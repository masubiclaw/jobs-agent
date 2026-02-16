"""Admin service for system management operations."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

# Import existing tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from job_agent_coordinator.tools.job_cache import get_cache

logger = logging.getLogger(__name__)


class AdminService:
    """
    Admin service for system management.
    
    Provides access to scraper, searcher, matcher, and cleanup operations.
    """
    
    def __init__(self):
        self._cache = get_cache()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        from api.auth import get_user_store
        
        cache_stats = self._cache.stats()
        user_store = get_user_store()
        
        return {
            "jobs": {
                "total": cache_stats.get("total_jobs", 0),
                "by_platform": cache_stats.get("platforms", {}),
                "top_companies": cache_stats.get("top_companies", [])[:10]
            },
            "matches": {
                "total": cache_stats.get("total_matches", 0),
                "stats": cache_stats.get("match_stats", {})
            },
            "vector_search": {
                "available": cache_stats.get("vector_search", False),
                "count": cache_stats.get("vector_count", 0)
            },
            "users": {
                "total": user_store.count()
            },
            "cache": {
                "dir": cache_stats.get("cache_dir"),
                "created": cache_stats.get("created"),
                "last_updated": cache_stats.get("last_updated"),
                "total_ever_added": cache_stats.get("total_ever_added", 0)
            }
        }
    
    def run_scraper(
        self,
        file_path: Optional[str] = None,
        categories: Optional[str] = None,
        max_sources: int = 0
    ):
        """Run job scraper in background."""
        try:
            from job_agent_coordinator.tools.job_links_scraper import scrape_job_links

            # Restrict file_path to .md files in the project root
            safe_path = file_path or "JobOpeningsLink.md"
            resolved = Path(safe_path).resolve()
            project_root = Path(".").resolve()
            if not str(resolved).startswith(str(project_root)) or not safe_path.endswith(".md"):
                logger.warning(f"Blocked scraper file path: {safe_path}")
                return

            logger.info(f"Starting scraper: file={safe_path}, categories={categories}, max={max_sources}")

            result = scrape_job_links(
                file_path=safe_path,
                categories=categories or "",
                max_sources=max_sources,
                cache_results=True,
                resume=True
            )
            
            logger.info(f"Scraper completed: {result}")
            
        except Exception as e:
            logger.error(f"Scraper failed: {e}", exc_info=True)
    
    def run_searcher(
        self,
        search_term: str,
        location: str = "",
        sites: str = "indeed,linkedin",
        results_wanted: int = 15
    ):
        """Run job searcher in background."""
        try:
            from job_agent_coordinator.tools.jobspy_tools import search_jobs_with_jobspy
            
            logger.info(f"Starting search: term={search_term}, location={location}, sites={sites}")
            
            result = search_jobs_with_jobspy(
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                sites=sites
            )
            
            logger.info(f"Search completed: {result}")
            
        except Exception as e:
            logger.error(f"Searcher failed: {e}", exc_info=True)
    
    def run_matcher(
        self,
        profile_id: Optional[str] = None,
        llm_pass: bool = False,
        limit: int = 100
    ):
        """Run job matcher in background."""
        try:
            # Import matcher
            from job_agent_coordinator.sub_agents.job_matcher.agent import analyze_job_match

            logger.info(f"Starting matcher: llm={llm_pass}, limit={limit}")

            # Get jobs to match
            jobs = self._cache.list_all(limit=limit)
            matched = 0

            for job in jobs:
                job_id = job.get("id", "")

                # Run analysis
                result = analyze_job_match(
                    job_title=job.get("title", ""),
                    company=job.get("company", ""),
                    job_description=job.get("description", ""),
                    location=job.get("location", ""),
                    salary_info=job.get("salary", ""),
                    job_url=job.get("url", ""),
                    job_id=job_id,
                    use_cache=True,
                    fetch_description=False,
                    run_llm=llm_pass
                )

                if result.get("success") and not result.get("from_cache"):
                    matched += 1

            logger.info(f"Matcher completed: matched {matched} new jobs")
            
        except Exception as e:
            logger.error(f"Matcher failed: {e}", exc_info=True)
    
    def run_cleanup(
        self,
        days_old: int = 30,
        check_urls: bool = False
    ):
        """Run cleanup in background."""
        try:
            logger.info(f"Starting cleanup: days_old={days_old}, check_urls={check_urls}")
            
            cutoff = datetime.now() - timedelta(days=days_old)
            removed = 0
            
            # Get all jobs
            jobs = self._cache.list_all(limit=10000)
            
            for job in jobs:
                cached_at = job.get("cached_at", "")
                if cached_at:
                    try:
                        job_date = datetime.fromisoformat(cached_at)
                        if job_date < cutoff:
                            self._cache.remove(job.get("id", ""))
                            removed += 1
                    except:
                        pass
            
            # Optionally check URLs
            if check_urls:
                import requests
                
                jobs = self._cache.list_all(limit=10000)
                for job in jobs:
                    url = job.get("url", "")
                    if url:
                        try:
                            response = requests.head(url, timeout=5, allow_redirects=True)
                            if response.status_code >= 400:
                                self._cache.remove(job.get("id", ""))
                                removed += 1
                        except:
                            pass
            
            logger.info(f"Cleanup completed: removed {removed} jobs")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
    
    def list_all_jobs(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """List all jobs (admin view)."""
        all_jobs = self._cache.list_all(limit=10000)
        
        total = len(all_jobs)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        jobs = [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "company": j.get("company"),
                "location": j.get("location"),
                "platform": j.get("platform"),
                "cached_at": j.get("cached_at"),
                "url": j.get("url")
            }
            for j in all_jobs[start_idx:end_idx]
        ]
        
        return {
            "jobs": jobs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": end_idx < total
        }
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the cache."""
        return self._cache.remove(job_id)
    
    def list_users(self) -> Dict[str, Any]:
        """List all users."""
        from api.auth import get_user_store

        user_store = get_user_store()
        users = user_store.list_users()

        return {
            "users": users,
            "total": len(users)
        }

    def delete_user(self, user_id: str) -> bool:
        """Delete a user by ID."""
        from api.auth import get_user_store

        user_store = get_user_store()
        return user_store.delete(user_id)
