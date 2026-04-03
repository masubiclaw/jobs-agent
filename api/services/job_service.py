"""Job service wrapping the existing JobCache with multi-user support."""

import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from api.models import (
    JobCreate, JobResponse, JobListResponse, JobStatus, JobAddMethod, MatchResult
)

# Import existing tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from job_agent_coordinator.tools.job_cache import get_cache, JobCache

logger = logging.getLogger(__name__)


class JobService:
    """
    Multi-user job service.
    
    Jobs are shared globally (scraped jobs), but user-specific metadata
    (status, notes) is stored per-user.
    """
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".job_cache/users")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cache = get_cache()
    
    def _user_jobs_file(self, user_id: str) -> Path:
        """Get user-specific job metadata file."""
        user_dir = self.base_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / "job_metadata.json"

    def _load_user_job_metadata(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Load user-specific job metadata."""
        meta_file = self._user_jobs_file(user_id)
        if meta_file.exists():
            try:
                data = json.loads(meta_file.read_text())
                return data.get("jobs", {}) if isinstance(data, dict) else {}
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning("Failed to load user job metadata: %s", e)
        return {}

    def _save_user_job_metadata(self, user_id: str, metadata: Dict[str, Dict[str, Any]]):
        """Save user-specific job metadata."""
        meta_file = self._user_jobs_file(user_id)
        data = {
            "jobs": metadata,
            "updated_at": datetime.now().isoformat()
        }
        meta_file.write_text(json.dumps(data, indent=2))
    
    def _get_user_job_meta(self, user_id: str, job_id: str) -> Dict[str, Any]:
        """Get user-specific metadata for a job."""
        all_meta = self._load_user_job_metadata(user_id)
        return all_meta.get(job_id, {
            "status": JobStatus.ACTIVE.value,
            "notes": "",
            "added_by": JobAddMethod.SCRAPED.value
        })
    
    def _set_user_job_meta(self, user_id: str, job_id: str, **kwargs):
        """Set user-specific metadata for a job."""
        all_meta = self._load_user_job_metadata(user_id)
        if job_id not in all_meta:
            all_meta[job_id] = {
                "status": JobStatus.ACTIVE.value,
                "notes": "",
                "added_by": JobAddMethod.SCRAPED.value
            }
        
        for key, value in kwargs.items():
            if value is not None:
                if hasattr(value, 'value'):
                    all_meta[job_id][key] = value.value
                else:
                    all_meta[job_id][key] = value
        
        self._save_user_job_metadata(user_id, all_meta)
    
    def _job_to_response(self, job: Dict[str, Any], user_meta: Dict[str, Any] = None, match: Dict[str, Any] = None) -> JobResponse:
        """Convert job dict to response model."""
        user_meta = user_meta or {}
        
        match_result = None
        if match:
            match_result = MatchResult(
                keyword_score=match.get("keyword_score", 0),
                llm_score=match.get("llm_score"),
                combined_score=match.get("combined_score", match.get("match_score", 0)),
                match_level=match.get("match_level", "unknown"),
                toon_report=match.get("toon_report", ""),
                cached_at=datetime.fromisoformat(match["cached_at"]) if match.get("cached_at") else None
            )
        
        return JobResponse(
            id=job.get("id", ""),
            title=user_meta.get("title", job.get("title", "Unknown")),
            company=user_meta.get("company", job.get("company", "Unknown")),
            location=user_meta.get("location", job.get("location", "Unknown")),
            salary=user_meta.get("salary", job.get("salary", "Not specified")),
            url=user_meta.get("url", job.get("url", "")),
            description=user_meta.get("description", job.get("description", "")),
            platform=job.get("platform", "unknown"),
            posted_date=job.get("posted_date", ""),
            cached_at=datetime.fromisoformat(job.get("cached_at", datetime.now().isoformat())),
            status=JobStatus(user_meta.get("status", JobStatus.ACTIVE.value)),
            added_by=JobAddMethod(user_meta.get("added_by", JobAddMethod.SCRAPED.value)),
            notes=user_meta.get("notes", ""),
            match=match_result
        )
    
    def list_jobs(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[JobStatus] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        query: Optional[str] = None,
        semantic: bool = False,
        sort_by: Optional[str] = None,
    ) -> JobListResponse:
        """List jobs with filters, sorting, and pagination."""
        # Get all jobs from cache (no limit — filtering + pagination applied below)
        if semantic and query:
            all_jobs = self._cache.semantic_search(query, limit=10000)
        elif query or company or location:
            all_jobs = self._cache.search(
                query=query or "",
                company=company or "",
                location=location or "",
                limit=10000
            )
        else:
            all_jobs = self._cache.list_all(limit=10000)

        # Load user metadata
        user_meta = self._load_user_job_metadata(user_id)

        # Apply status filter
        filtered_jobs = []
        for job in all_jobs:
            job_id = job.get("id", "")
            meta = user_meta.get(job_id, {"status": JobStatus.ACTIVE.value})

            if status and meta.get("status") != status.value:
                continue

            filtered_jobs.append((job, meta))

        # Sort
        if sort_by == "date":
            filtered_jobs.sort(key=lambda x: x[0].get("cached_at", ""), reverse=True)
        elif sort_by == "company":
            filtered_jobs.sort(key=lambda x: x[0].get("company", "").lower())
        elif sort_by == "title":
            filtered_jobs.sort(key=lambda x: x[0].get("title", "").lower())
        elif sort_by == "score":
            def _score(item):
                m = self._cache.get_match(item[0].get("id", ""))
                return m.get("combined_score", 0) if m else 0
            filtered_jobs.sort(key=_score, reverse=True)

        # Pagination
        total = len(filtered_jobs)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_jobs = filtered_jobs[start_idx:end_idx]

        # Convert to response
        jobs = []
        for job, meta in page_jobs:
            job_id = job.get("id", "")
            match = self._cache.get_match(job_id)
            jobs.append(self._job_to_response(job, meta, match))

        return JobListResponse(
            jobs=jobs,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end_idx < total
        )
    
    def get_top_matches(
        self,
        user_id: str,
        limit: int = 10,
        min_score: int = 0
    ) -> List[JobResponse]:
        """Get top matched jobs, filtering out archived and excluded companies."""
        matches = self._cache.list_matches(min_score=min_score, limit=limit * 3)
        user_meta = self._load_user_job_metadata(user_id)

        # Load excluded companies from user's API profile
        from api.services.profile_service import ProfileService
        excluded = []
        try:
            ps = ProfileService()
            profile = ps.get_active_profile(user_id)
            if profile and profile.preferences:
                excluded = [c.lower() for c in profile.preferences.excluded_companies]
        except Exception:
            pass

        jobs = []
        for match in matches:
            job_id = match.get("job_id", "")
            job = self._cache.get(job_id)
            if not job:
                continue
            meta = user_meta.get(job_id, {"status": JobStatus.ACTIVE.value})
            # Skip archived/not-interested jobs
            if meta.get("status") == JobStatus.ARCHIVED.value:
                continue
            # Skip excluded companies
            company = job.get("company", "").lower()
            if any(exc in company for exc in excluded):
                continue
            jobs.append(self._job_to_response(job, meta, match))
            if len(jobs) >= limit:
                break

        return jobs
    
    def create_job(self, user_id: str, job_data: JobCreate) -> Optional[JobResponse]:
        """Create a new job from various input methods."""
        job = None
        added_by = JobAddMethod.MANUAL
        
        # Method 1: From URL
        if job_data.job_url:
            try:
                from job_agent_coordinator.tools.url_job_fetcher import fetch_job_from_url
                result = fetch_job_from_url(job_data.job_url)
                if result and isinstance(result, dict):
                    job = result
                    added_by = JobAddMethod.URL
            except Exception as e:
                logger.error(f"Failed to fetch job from URL: {e}")
        
        # Method 2: From plaintext (parse with LLM)
        elif job_data.plaintext:
            job = self._parse_plaintext_job(job_data.plaintext)
            added_by = JobAddMethod.MANUAL
        
        # Method 3: Direct fields
        elif job_data.title and job_data.title.strip() and job_data.company and job_data.company.strip():
            job = {
                "title": job_data.title,
                "company": job_data.company,
                "location": job_data.location or "Unknown",
                "description": job_data.description or "",
                "url": job_data.url or "",
                "salary": job_data.salary or "Not specified",
            }
            added_by = JobAddMethod.MANUAL
        
        if not job:
            return None
        
        # Add to cache
        self._cache.add(job)
        self._cache.flush()
        
        job_id = self._cache.generate_id(job)
        
        # Set user metadata
        self._set_user_job_meta(user_id, job_id, added_by=added_by, status=JobStatus.ACTIVE)
        
        return self._job_to_response(
            self._cache.get(job_id),
            self._get_user_job_meta(user_id, job_id)
        )
    
    def _parse_plaintext_job(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse job description from plaintext using LLM."""
        try:
            import ollama
            
            prompt = f"""Extract job details from this text. Return ONLY a JSON object with these fields:
- title: Job title
- company: Company name  
- location: Job location
- salary: Salary if mentioned, otherwise "Not specified"
- description: Brief description (max 500 chars)

Text:
{text[:3000]}

JSON:"""
            
            response = ollama.chat(
                model="gemma3:12b",
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}
            )
            
            import json
            content = response["message"]["content"]
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"Failed to parse plaintext job: {e}")
            return None
    
    def create_job_from_pdf(self, user_id: str, pdf_content: bytes, filename: str) -> Optional[JobResponse]:
        """Create job from PDF upload."""
        try:
            import fitz  # PyMuPDF
            
            # Extract text from PDF
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            
            if not text.strip():
                return None
            
            # Parse with LLM
            job = self._parse_plaintext_job(text)
            if not job:
                return None
            
            # Add to cache
            self._cache.add(job)
            self._cache.flush()
            
            job_id = self._cache.generate_id(job)
            
            # Set user metadata
            self._set_user_job_meta(user_id, job_id, added_by=JobAddMethod.PDF, status=JobStatus.ACTIVE)
            
            return self._job_to_response(
                self._cache.get(job_id),
                self._get_user_job_meta(user_id, job_id)
            )
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            return None
    
    def get_job(self, job_id: str, user_id: str) -> Optional[JobResponse]:
        """Get a job by ID."""
        job = self._cache.get(job_id)
        if not job:
            return None
        
        meta = self._get_user_job_meta(user_id, job_id)
        match = self._cache.get_match(job_id)
        
        return self._job_to_response(job, meta, match)
    
    def update_job(self, job_id: str, user_id: str, **kwargs) -> Optional[JobResponse]:
        """Update user-specific job metadata."""
        job = self._cache.get(job_id)
        if not job:
            return None
        
        # Update user metadata
        self._set_user_job_meta(user_id, job_id, **kwargs)
        
        meta = self._get_user_job_meta(user_id, job_id)
        match = self._cache.get_match(job_id)
        
        return self._job_to_response(job, meta, match)
    
    def delete_job(self, job_id: str, user_id: str) -> bool:
        """Delete a job and remove from cache."""
        # Remove user metadata
        all_meta = self._load_user_job_metadata(user_id)
        had_meta = job_id in all_meta
        if had_meta:
            del all_meta[job_id]
            self._save_user_job_metadata(user_id, all_meta)

        # Also remove from global cache
        job = self._cache.get(job_id)
        if job:
            self._cache.remove(job_id)
            self._cache.flush()
            return True

        return had_meta
