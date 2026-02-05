"""Admin routes for system management."""

from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query, BackgroundTasks

from api.models import UserResponse
from api.auth import get_current_admin_user
from api.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin"])


def get_admin_service() -> AdminService:
    """Dependency to get admin service."""
    return AdminService()


@router.get("/stats")
async def get_system_stats(
    current_user: UserResponse = Depends(get_current_admin_user),
    service: AdminService = Depends(get_admin_service)
) -> dict:
    """Get system statistics (job counts, user counts, etc.)."""
    return service.get_stats()


@router.post("/scraper/run")
async def run_scraper(
    background_tasks: BackgroundTasks,
    file_path: Optional[str] = Query(None, description="Path to markdown file with job links"),
    categories: Optional[str] = Query(None, description="Comma-separated categories to scrape"),
    max_sources: int = Query(0, description="Maximum sources to scrape (0 for all)"),
    current_user: UserResponse = Depends(get_current_admin_user),
    service: AdminService = Depends(get_admin_service)
) -> dict:
    """
    Run the job scraper in the background.
    
    Scrapes job listings from company career pages defined in JobOpeningsLink.md.
    """
    background_tasks.add_task(
        service.run_scraper,
        file_path=file_path,
        categories=categories,
        max_sources=max_sources
    )
    
    return {
        "status": "started",
        "message": "Scraper started in background. Check stats for progress."
    }


@router.post("/searcher/run")
async def run_searcher(
    background_tasks: BackgroundTasks,
    search_term: str = Query(..., description="Job search term"),
    location: str = Query("", description="Location to search"),
    sites: str = Query("indeed,linkedin", description="Comma-separated sites to search"),
    results_wanted: int = Query(15, ge=1, le=50),
    current_user: UserResponse = Depends(get_current_admin_user),
    service: AdminService = Depends(get_admin_service)
) -> dict:
    """
    Run job search on aggregators.
    
    Searches Indeed, LinkedIn, Glassdoor, etc. for job listings.
    """
    background_tasks.add_task(
        service.run_searcher,
        search_term=search_term,
        location=location,
        sites=sites,
        results_wanted=results_wanted
    )
    
    return {
        "status": "started",
        "message": f"Searching for '{search_term}' jobs. Check stats for results."
    }


@router.post("/matcher/run")
async def run_matcher(
    background_tasks: BackgroundTasks,
    profile_id: Optional[str] = Query(None, description="Profile ID to match against"),
    llm_pass: bool = Query(False, description="Run LLM pass (slower but more accurate)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum jobs to match"),
    current_user: UserResponse = Depends(get_current_admin_user),
    service: AdminService = Depends(get_admin_service)
) -> dict:
    """
    Run job matcher on cached jobs.
    
    Analyzes cached jobs against user profile using keyword and optional LLM matching.
    """
    background_tasks.add_task(
        service.run_matcher,
        profile_id=profile_id,
        llm_pass=llm_pass,
        limit=limit
    )
    
    return {
        "status": "started",
        "message": f"Matching jobs against profile. LLM pass: {llm_pass}"
    }


@router.post("/cleanup")
async def run_cleanup(
    background_tasks: BackgroundTasks,
    days_old: int = Query(30, ge=1, description="Remove jobs older than this many days"),
    check_urls: bool = Query(False, description="Check if job URLs are still valid"),
    current_user: UserResponse = Depends(get_current_admin_user),
    service: AdminService = Depends(get_admin_service)
) -> dict:
    """
    Clean up dead or expired job listings.
    
    Removes old jobs and optionally checks if job posting URLs are still valid.
    """
    background_tasks.add_task(
        service.run_cleanup,
        days_old=days_old,
        check_urls=check_urls
    )
    
    return {
        "status": "started",
        "message": f"Cleanup started. Removing jobs older than {days_old} days."
    }


@router.get("/jobs")
async def list_all_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_admin_user),
    service: AdminService = Depends(get_admin_service)
) -> dict:
    """List all jobs in the system (admin view)."""
    return service.list_all_jobs(page=page, page_size=page_size)


@router.delete("/jobs/{job_id}")
async def admin_delete_job(
    job_id: str,
    current_user: UserResponse = Depends(get_current_admin_user),
    service: AdminService = Depends(get_admin_service)
) -> dict:
    """Delete any job (admin only)."""
    success = service.delete_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return {"status": "deleted", "job_id": job_id}


@router.get("/users")
async def list_users(
    current_user: UserResponse = Depends(get_current_admin_user),
    service: AdminService = Depends(get_admin_service)
) -> dict:
    """List all users (admin only)."""
    return service.list_users()
