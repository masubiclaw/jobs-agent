"""Local file-based cache tool for job search data."""

import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from google.adk.tools import FunctionTool
except ImportError:
    FunctionTool = lambda func: func

from .toon_format import to_toon, from_toon

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("JOB_AGENT_CACHE", ".job_cache"))


class LocalCache:
    """TOON file cache for job search data (with JSON fallback for migration)."""
    
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # TOON format files
        self.exclusions_file = self.cache_dir / "exclusions.toon"
        self.settings_file = self.cache_dir / "settings.toon"
        
        # Legacy JSON files (for migration)
        self._exclusions_json = self.cache_dir / "exclusions.json"
        self._settings_json = self.cache_dir / "settings.json"
        
        # Note: jobs are now in job_cache.py, not here
        self.jobs_file = None  # Deprecated - use JobCache instead
    
    def get_exclusions(self) -> list[str]:
        return self._load(self.exclusions_file).get("companies", [])
    
    def add_exclusion(self, company: str) -> list[str]:
        data = self._load(self.exclusions_file)
        companies = data.get("companies", [])
        c = company.lower().strip()
        if c and c not in [x.lower() for x in companies]:
            companies.append(c)
            self._save(self.exclusions_file, {"companies": companies, "updated": datetime.now().isoformat()})
            logger.info(f"➕ Exclusion: {c}")
        return companies
    
    def remove_exclusion(self, company: str) -> list[str]:
        data = self._load(self.exclusions_file)
        companies = [c for c in data.get("companies", []) if c.lower() != company.lower().strip()]
        self._save(self.exclusions_file, {"companies": companies, "updated": datetime.now().isoformat()})
        return companies
    
    def clear_exclusions(self):
        self._save(self.exclusions_file, {"companies": [], "updated": datetime.now().isoformat()})
    
    def get_jobs(self, search_term: str = None, location: str = None) -> list[dict]:
        jobs = self._load(self.jobs_file).get("jobs", [])
        if search_term:
            jobs = [j for j in jobs if search_term.lower() in j.get("search_term", "").lower()]
        if location:
            jobs = [j for j in jobs if location.lower() in j.get("location", "").lower()]
        return jobs
    
    def cache_jobs(self, jobs: list[dict], search_term: str, location: str) -> int:
        data = self._load(self.jobs_file)
        existing = data.get("jobs", [])
        urls = {j.get("url") for j in existing}
        ts = datetime.now().isoformat()
        new_count = 0
        for job in jobs:
            if job.get("url") and job["url"] not in urls:
                job.update({"cached_at": ts, "search_term": search_term, "search_location": location})
                existing.append(job)
                urls.add(job["url"])
                new_count += 1
        self._save(self.jobs_file, {"jobs": existing, "updated": ts})
        if new_count:
            logger.info(f"💾 Cached {new_count} jobs (total: {len(existing)})")
        return new_count
    
    def clear_jobs(self):
        self._save(self.jobs_file, {"jobs": [], "updated": datetime.now().isoformat()})
    
    def get_stats(self) -> dict:
        jobs = self._load(self.jobs_file).get("jobs", [])
        return {"total": len(jobs), "companies": len(set(j.get("company", "") for j in jobs))}
    
    def _load(self, path: Path) -> dict:
        """Load from TOON file, with JSON fallback for migration."""
        if path.exists():
            try:
                return from_toon(path.read_text())
            except:
                pass
        
        # Try JSON fallback (for migration)
        json_path = path.with_suffix('.json')
        if json_path.exists():
            try:
                data = json.load(open(json_path))
                logger.info(f"📦 Migrating {json_path.name} to TOON format...")
                return data
            except:
                pass
        
        return {}
    
    def _save(self, path: Path, data: dict):
        """Save in TOON format."""
        path.write_text(to_toon(data) + '\n')


_cache: Optional[LocalCache] = None

def get_cache() -> LocalCache:
    global _cache
    if _cache is None:
        _cache = LocalCache()
    return _cache


# === Tool Functions (for agents) ===

def get_exclusions() -> str:
    """Get list of excluded companies."""
    exclusions = get_cache().get_exclusions()
    lines = [
        "[excluded_companies]",
        f"total: {len(exclusions)}",
        ""
    ]
    for c in exclusions:
        lines.append(f"- {c}")
    if not exclusions:
        lines.append("- none")
    return "\n".join(lines)

def add_exclusion(company: str) -> str:
    """Add a company to the exclusion list."""
    exclusions = get_cache().add_exclusion(company)
    return f"[exclusion_added]\ncompany: {company.lower().strip()}\ntotal_exclusions: {len(exclusions)}"

def remove_exclusion(company: str) -> str:
    """Remove a company from the exclusion list."""
    exclusions = get_cache().remove_exclusion(company)
    return f"[exclusion_removed]\ncompany: {company}\ntotal_exclusions: {len(exclusions)}"

def get_cached_jobs(search_term: str = "", location: str = "") -> str:
    """Get cached jobs, optionally filtered."""
    jobs = get_cache().get_jobs(search_term or None, location or None)
    lines = [
        "[local_cached_jobs]",
        f"search_term: {search_term or 'all'}",
        f"location: {location or 'all'}",
        f"results: {len(jobs)}",
        ""
    ]
    for i, job in enumerate(jobs[:20], 1):
        lines.append(f"{i}. {job.get('title', 'Unknown')[:40]} @ {job.get('company', 'Unknown')[:20]}")
    if not jobs:
        lines.append("- no jobs found")
    return "\n".join(lines)

def get_cache_stats() -> str:
    """Get local cache statistics."""
    stats = get_cache().get_stats()
    lines = [
        "[local_cache_stats]",
        f"exclusions: {stats.get('exclusions', 0)}",
        f"jobs: {stats.get('jobs', 0)}",
        f"cache_dir: {stats.get('cache_dir', 'unknown')}"
    ]
    return "\n".join(lines)


# === FunctionTools ===

get_exclusions_tool = FunctionTool(func=get_exclusions)
add_exclusion_tool = FunctionTool(func=add_exclusion)
remove_exclusion_tool = FunctionTool(func=remove_exclusion)
get_cached_jobs_tool = FunctionTool(func=get_cached_jobs)
get_cache_stats_tool = FunctionTool(func=get_cache_stats)
