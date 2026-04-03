"""Pipeline scheduler service for running the job pipeline on a schedule."""

import asyncio
import logging
import time
import hashlib
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from job_agent_coordinator.tools.toon_format import to_toon, from_toon
from job_agent_coordinator.tools.job_cache import get_cache
from job_agent_coordinator.tools.profile_store import get_store
from api.services.profile_service import ProfileService

logger = logging.getLogger(__name__)


class PipelineLogHandler(logging.Handler):
    """Custom log handler that writes to a ring buffer."""

    def __init__(self, buffer: deque):
        super().__init__()
        self.buffer = buffer

    def emit(self, record):
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "level": record.levelname,
                "message": self.format(record),
            }
            self.buffer.append(entry)
        except Exception:
            pass


class PipelineService:
    """Manages pipeline scheduling, execution, and history."""

    _instance: Optional["PipelineService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._scheduler_enabled = False
        self._interval_hours = 24.0
        self._is_running = False
        self._current_step: Optional[str] = None
        self._last_run: Optional[datetime] = None
        self._next_run: Optional[datetime] = None
        self._scheduler_task: Optional[asyncio.Task] = None

        self._log_buffer: deque = deque(maxlen=1000)
        self._log_handler = PipelineLogHandler(self._log_buffer)
        self._log_handler.setFormatter(logging.Formatter("%(message)s"))

        self._history_file = Path(".job_cache/pipeline_runs.toon")
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        self._user_id: Optional[str] = None

    def _load_history(self) -> List[Dict[str, Any]]:
        if self._history_file.exists():
            try:
                data = from_toon(self._history_file.read_text())
                return data.get("runs", []) if isinstance(data, dict) else []
            except Exception:
                pass
        return []

    def _save_history(self, runs: List[Dict[str, Any]]):
        data = {"runs": runs[-100:], "updated_at": datetime.now().isoformat()}
        self._history_file.write_text(to_toon(data) + "\n")

    def _add_log(self, level: str, message: str):
        self._log_buffer.append({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
        })

    def get_status(self) -> dict:
        return {
            "scheduler_enabled": self._scheduler_enabled,
            "interval_hours": self._interval_hours,
            "is_running": self._is_running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "next_run": self._next_run.isoformat() if self._next_run else None,
            "current_step": self._current_step,
        }

    def get_history(self, limit: int = 20) -> List[dict]:
        runs = self._load_history()
        return list(reversed(runs[-limit:]))

    def get_logs(self, limit: int = 200) -> List[dict]:
        logs = list(self._log_buffer)
        return logs[-limit:]

    def get_stats(self) -> dict:
        runs = self._load_history()
        completed = [r for r in runs if r.get("status") == "success"]
        failed = [r for r in runs if r.get("status") == "failed"]

        durations = [r["duration_seconds"] for r in completed if r.get("duration_seconds")]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_runs": len(runs),
            "successful_runs": len(completed),
            "failed_runs": len(failed),
            "avg_duration_seconds": round(avg_duration, 1),
            "total_jobs_found": sum(r.get("jobs_found", 0) for r in runs),
            "total_jobs_matched": sum(r.get("jobs_matched", 0) for r in runs),
            "total_docs_generated": sum(r.get("docs_generated", 0) for r in runs),
        }

    def start_scheduler(self, interval_hours: float, user_id: Optional[str] = None, start_time: Optional[str] = None):
        self._scheduler_enabled = True
        self._interval_hours = interval_hours
        if user_id:
            self._user_id = user_id

        if start_time:
            # Parse HH:MM and schedule first run at that time today (or tomorrow if past)
            try:
                hour, minute = map(int, start_time.split(":"))
                now = datetime.now()
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                self._next_run = next_run
                self._add_log("INFO", f"Scheduler started with {interval_hours}h interval, first run at {start_time}")
            except (ValueError, AttributeError):
                self._next_run = datetime.now() + timedelta(hours=interval_hours)
                self._add_log("WARNING", f"Invalid start_time '{start_time}', using interval offset")
        else:
            self._next_run = datetime.now() + timedelta(hours=interval_hours)
            self._add_log("INFO", f"Scheduler started with {interval_hours}h interval")

        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()

        loop = asyncio.get_running_loop()
        self._scheduler_task = loop.create_task(self._scheduler_loop())

    def stop_scheduler(self):
        self._scheduler_enabled = False
        self._next_run = None
        self._add_log("INFO", "Scheduler stopped")

        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            self._scheduler_task = None

    async def _scheduler_loop(self):
        try:
            while self._scheduler_enabled:
                # On first iteration, honour _next_run set by start_scheduler
                # (e.g. from start_time). On subsequent iterations, schedule
                # the next run relative to now.
                if self._next_run and self._next_run > datetime.now():
                    wait_seconds = (self._next_run - datetime.now()).total_seconds()
                else:
                    wait_seconds = self._interval_hours * 3600
                    self._next_run = datetime.now() + timedelta(seconds=wait_seconds)
                self._add_log("INFO", f"Next run scheduled at {self._next_run.isoformat()}")

                await asyncio.sleep(wait_seconds)
                # Clear so next iteration recalculates from interval
                self._next_run = None

                if self._scheduler_enabled and not self._is_running:
                    await self._execute_pipeline(
                        steps=["search", "clean", "fetch", "match", "generate"]
                    )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._add_log("ERROR", f"Scheduler error: {e}")

    def _get_user_search_context(self) -> Dict[str, Any]:
        """Get search context from user's API profile, falling back to global store."""
        if self._user_id:
            try:
                profile_service = ProfileService()
                profile = profile_service.get_active_profile(self._user_id)
                if profile:
                    prefs = profile.preferences
                    return {
                        "name": profile.name,
                        "location": profile.location,
                        "skills": [s.name for s in profile.skills],
                        "target_roles": prefs.target_roles if prefs else [],
                        "target_locations": prefs.target_locations if prefs else [],
                        "remote_preference": prefs.remote_preference if prefs else None,
                        "excluded_companies": prefs.excluded_companies if prefs else [],
                    }
            except Exception as e:
                self._add_log("WARNING", f"Failed to load user profile: {e}")

        # Fall back to global store
        return get_store().get_search_context()

    async def run_pipeline_now(self, steps: List[str], user_id: Optional[str] = None):
        valid_steps = {"search", "clean", "fetch", "match", "generate"}
        invalid = set(steps) - valid_steps
        if invalid:
            raise ValueError(f"Invalid pipeline steps: {invalid}")
        if self._is_running:
            self._add_log("WARNING", "Pipeline already running, skipping")
            return
        self._user_id = user_id
        await self._execute_pipeline(steps)

    async def _execute_pipeline(self, steps: List[str]):
        self._is_running = True
        run_id = hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:10]
        start_time = time.time()
        self._last_run = datetime.now()

        run_record = {
            "id": run_id,
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "duration_seconds": None,
            "status": "running",
            "steps": steps,
            "jobs_found": 0,
            "jobs_matched": 0,
            "docs_generated": 0,
            "error": None,
        }

        self._add_log("INFO", f"Pipeline run {run_id} started with steps: {', '.join(steps)}")

        try:
            cache = get_cache()

            if "search" in steps:
                self._current_step = "search"
                self._add_log("INFO", "Step: SEARCH")
                jobs_found = await self._run_search_step()
                run_record["jobs_found"] = jobs_found
                self._add_log("INFO", f"Search complete: {jobs_found} jobs found")

            if "clean" in steps:
                self._current_step = "clean"
                self._add_log("INFO", "Step: CLEAN")
                removed = await self._run_clean_step(cache)
                self._add_log("INFO", f"Clean complete: {removed} jobs removed")

            if "fetch" in steps:
                self._current_step = "fetch"
                self._add_log("INFO", "Step: FETCH DESCRIPTIONS")
                fetched = await self._run_fetch_step(cache)
                self._add_log("INFO", f"Fetch complete: {fetched} descriptions fetched")

            if "match" in steps:
                self._current_step = "match"
                self._add_log("INFO", "Step: MATCH")
                matched = await self._run_match_step(cache)
                run_record["jobs_matched"] = matched
                self._add_log("INFO", f"Match complete: {matched} good matches")

            if "generate" in steps:
                self._current_step = "generate"
                self._add_log("INFO", "Step: GENERATE")
                generated = await self._run_generate_step(cache)
                run_record["docs_generated"] = generated
                self._add_log("INFO", f"Generate complete: {generated} documents")

            run_record["status"] = "success"
            self._add_log("INFO", f"Pipeline run {run_id} completed successfully")

        except Exception as e:
            run_record["status"] = "failed"
            run_record["error"] = str(e)
            self._add_log("ERROR", f"Pipeline run {run_id} failed: {e}")
            logger.error(f"Pipeline error: {e}", exc_info=True)

        finally:
            elapsed = time.time() - start_time
            run_record["finished_at"] = datetime.now().isoformat()
            run_record["duration_seconds"] = round(elapsed, 1)
            self._is_running = False
            self._current_step = None

            # Save to history
            runs = self._load_history()
            runs.append(run_record)
            self._save_history(runs)

    async def _run_search_step(self) -> int:
        """Run job search. Returns number of jobs found."""
        try:
            from job_agent_coordinator.tools.jobspy_tools import (
                search_jobs_with_jobspy,
                JOBSPY_AVAILABLE,
            )

            if not JOBSPY_AVAILABLE:
                self._add_log("WARNING", "JobSpy not available, skipping search")
                return 0

            context = self._get_user_search_context()
            exclusions = context.get("excluded_companies", [])

            # Build search terms from profile target_roles, fall back to defaults
            target_roles = context.get("target_roles", [])
            location = context.get("location") or "seattle"
            target_locations = context.get("target_locations", [])

            # Use profile roles or expand with common variants
            if target_roles:
                search_terms = target_roles
            else:
                search_terms = [
                    "software engineer",
                    "senior software engineer",
                    "full stack developer",
                ]

            # Use profile locations or expand with common tech hubs
            if target_locations:
                search_locations = list(dict.fromkeys(
                    [location] + target_locations
                ))
            else:
                search_locations = list(dict.fromkeys([
                    location,
                    "remote",
                ]))

            total_found = 0
            for term in search_terms:
                for loc in search_locations:
                    self._add_log("INFO", f"Searching: '{term}' in '{loc}'")
                    result = await asyncio.to_thread(
                        search_jobs_with_jobspy,
                        search_term=term,
                        location=loc,
                        results_wanted=100,
                        hours_old=168,
                        sites="indeed,linkedin,glassdoor,zip_recruiter",
                        exclude_companies=",".join(exclusions) if exclusions else "",
                    )

                    if result.get("success"):
                        found = len(result.get("jobs", []))
                        total_found += found
                        self._add_log("INFO", f"Found {found} jobs for '{term}' in '{loc}'")
                    else:
                        self._add_log("WARNING", f"Search failed for '{term}' in '{loc}': {result.get('error', 'unknown')}")
                        # Retry with fewer sites on failure
                        result = await asyncio.to_thread(
                            search_jobs_with_jobspy,
                            search_term=term,
                            location=loc,
                            results_wanted=50,
                            hours_old=336,
                            sites="indeed,zip_recruiter",
                            exclude_companies=",".join(exclusions) if exclusions else "",
                        )
                        if result.get("success"):
                            found = len(result.get("jobs", []))
                            total_found += found
                            self._add_log("INFO", f"Retry found {found} jobs for '{term}' in '{loc}'")

            return total_found

        except Exception as e:
            self._add_log("ERROR", f"Search error: {e}")
            return 0

    async def _run_clean_step(self, cache) -> int:
        """Clean dead jobs. Returns number removed."""
        try:
            all_jobs = cache.list_all(limit=100000)
            removed = 0

            for job in all_jobs:
                url = job.get("url", "").strip()
                if not url:
                    if cache.remove(job["id"]):
                        removed += 1
                    cache.clear_matches(job["id"])

            return removed
        except Exception as e:
            self._add_log("ERROR", f"Clean error: {e}")
            return 0

    async def _run_fetch_step(self, cache) -> int:
        """Fetch missing descriptions via Playwright (no LLM). Returns number fetched."""
        try:
            import concurrent.futures
            from job_agent_coordinator.tools.url_job_fetcher import fetch_page_with_playwright

            all_jobs = cache.list_all(limit=10000)
            without_desc = [
                j for j in all_jobs
                if not j.get("description", "").strip() and j.get("url", "").strip()
            ]

            if not without_desc:
                self._add_log("INFO", "All jobs already have descriptions")
                return 0

            batch_size = 200
            batch = without_desc[:batch_size]
            self._add_log("INFO", f"Fetching descriptions for {len(batch)} of {len(without_desc)} jobs...")

            fetched = 0
            for i, job in enumerate(batch):
                url = job.get("url", "")
                if not url:
                    continue
                try:
                    # Run Playwright in separate thread to avoid asyncio conflict
                    page_data = await asyncio.to_thread(
                        self._fetch_page_in_thread, url
                    )
                    if page_data and len(page_data.get("text", "")) > 100:
                        desc = page_data["text"][:8000]
                        cache.update_job(job["id"], description=desc)
                        fetched += 1
                except Exception as e:
                    self._add_log("DEBUG", f"Fetch failed for {url[:60]}: {e}")
                if (i + 1) % 25 == 0:
                    self._add_log("INFO", f"  Fetched {fetched}/{i + 1} descriptions")
                await asyncio.sleep(0.3)

            self._add_log("INFO", f"Fetch complete: {fetched} descriptions added")
            return fetched
        except Exception as e:
            self._add_log("ERROR", f"Fetch error: {e}")
            return 0

    @staticmethod
    def _fetch_page_in_thread(url: str):
        """Run Playwright in a clean thread (no asyncio loop)."""
        import concurrent.futures
        from job_agent_coordinator.tools.url_job_fetcher import fetch_page_with_playwright
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(fetch_page_with_playwright, url).result(timeout=45)

    async def _run_match_step(self, cache) -> int:
        """Run job matching. Returns number of good matches."""
        try:
            from job_agent_coordinator.sub_agents.job_matcher.agent import analyze_job_match

            jobs = cache.list_all(limit=500)
            good_matches = 0

            for job in jobs:
                try:
                    result = await asyncio.to_thread(
                        analyze_job_match,
                        job_title=job["title"],
                        company=job["company"],
                        job_description=job.get("description", ""),
                        location=job.get("location", ""),
                        salary_info=str(job.get("salary", "")),
                        job_url=job.get("url", ""),
                        job_id=job.get("id", ""),
                        use_cache=True,
                        run_llm=False,
                    )
                    level = result.get("match_level", "weak")
                    if level in ("strong", "good"):
                        good_matches += 1
                except Exception as e:
                    logger.debug(f"Match failed for job {job.get('id', '?')}: {e}")

            return good_matches
        except Exception as e:
            self._add_log("ERROR", f"Match error: {e}")
            return 0

    async def _run_generate_step(self, cache) -> int:
        """Generate documents for top matches. Returns count generated."""
        try:
            from job_agent_coordinator.tools.resume_tools import generate_application_package

            matches = cache.list_matches(min_score=60, limit=100)
            generated = 0

            for match in matches[:10]:
                job_id = match.get("job_id", "")
                try:
                    result = await asyncio.to_thread(
                        generate_application_package, job_id, ""
                    )
                    if result and "[error]" not in str(result).lower():
                        generated += 1
                    else:
                        self._add_log("WARN", f"Generate returned error for job {job_id}")
                except Exception as e:
                    self._add_log("WARN", f"Generate failed for job {job_id}: {e}")

            return generated
        except Exception as e:
            self._add_log("ERROR", f"Generate error: {e}")
            return 0


# Singleton accessor
def get_pipeline_service() -> PipelineService:
    return PipelineService()
