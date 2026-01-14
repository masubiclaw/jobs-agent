"""JobSpy tools for direct job scraping from LinkedIn, Indeed, Glassdoor, ZipRecruiter."""

import logging
from typing import Optional

from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

# Check if JobSpy is available
try:
    from jobspy import scrape_jobs
    JOBSPY_AVAILABLE = True
    logger.info("✅ JobSpy library available for direct job scraping")
except ImportError:
    JOBSPY_AVAILABLE = False
    logger.warning("⚠️ JobSpy not installed. Install with: pip install python-jobspy")


def search_jobs_with_jobspy(
    search_term: str,
    location: str,
    results_wanted: int = 15,
    hours_old: int = 72,
    sites: str = "indeed,linkedin"
) -> dict:
    """
    Search for jobs using JobSpy - a direct scraper for job platforms.
    
    This is MORE RELIABLE than google_search because it returns:
    - Direct job URLs (not search result snippets)
    - Accurate salary data
    - Posting dates
    - Company names
    
    Args:
        search_term: Job title/role to search (e.g., "software engineering manager")
        location: Location to search (e.g., "Seattle, WA")
        results_wanted: Number of results to fetch (default 15)
        hours_old: Only jobs posted within this many hours (default 72 = 3 days)
        sites: Comma-separated platforms: indeed,linkedin,glassdoor,zip_recruiter
    
    Returns:
        Dict with jobs list and metadata
    """
    if not JOBSPY_AVAILABLE:
        return {
            "success": False,
            "error": "JobSpy not installed. Install with: pip install python-jobspy",
            "jobs": []
        }
    
    try:
        # Parse sites
        site_list = [s.strip() for s in sites.split(",") if s.strip()]
        valid_sites = ["indeed", "linkedin", "glassdoor", "zip_recruiter"]
        site_list = [s for s in site_list if s in valid_sites]
        
        if not site_list:
            site_list = ["indeed", "linkedin"]
        
        logger.info(f"🔍 JobSpy searching: '{search_term}' in {location}")
        logger.info(f"   Sites: {site_list}, Results: {results_wanted}, Hours: {hours_old}")
        
        # Scrape jobs
        jobs_df = scrape_jobs(
            site_name=site_list,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed="USA"
        )
        
        # Convert to list of dicts
        jobs = []
        for _, row in jobs_df.iterrows():
            job = {
                "title": str(row.get("title", "Unknown")),
                "company": str(row.get("company", "Unknown")),
                "location": str(row.get("location", location)),
                "url": str(row.get("job_url", "")),
                "platform": str(row.get("site", "unknown")),
                "posted_date": str(row.get("date_posted", "")),
                "salary_min": row.get("min_amount") if not str(row.get("min_amount", "nan")).lower() == "nan" else None,
                "salary_max": row.get("max_amount") if not str(row.get("max_amount", "nan")).lower() == "nan" else None,
                "salary_currency": str(row.get("currency", "USD")),
                "job_type": str(row.get("job_type", "")),
                "description_snippet": str(row.get("description", ""))[:500] if row.get("description") else ""
            }
            
            # Format salary string
            if job["salary_min"] and job["salary_max"]:
                job["salary"] = f"${job['salary_min']:,.0f} - ${job['salary_max']:,.0f}"
            elif job["salary_min"]:
                job["salary"] = f"${job['salary_min']:,.0f}+"
            elif job["salary_max"]:
                job["salary"] = f"Up to ${job['salary_max']:,.0f}"
            else:
                job["salary"] = "Not disclosed"
            
            jobs.append(job)
            
            # Log each job found
            logger.info(f"📦 Found: {job['title']} @ {job['company']} [{job['platform']}]")
            logger.info(f"   🔗 {job['url']}")
        
        logger.info(f"✅ JobSpy found {len(jobs)} jobs total")
        
        return {
            "success": True,
            "count": len(jobs),
            "search_term": search_term,
            "location": location,
            "sites_searched": site_list,
            "jobs": jobs
        }
        
    except Exception as e:
        logger.error(f"❌ JobSpy error: {e}")
        return {
            "success": False,
            "error": str(e),
            "jobs": []
        }


def check_jobspy_status() -> dict:
    """
    Check if JobSpy is available and working.
    
    Returns:
        Status dict with availability and supported platforms
    """
    return {
        "available": JOBSPY_AVAILABLE,
        "supported_platforms": ["indeed", "linkedin", "glassdoor", "zip_recruiter"] if JOBSPY_AVAILABLE else [],
        "message": "JobSpy ready for direct job scraping" if JOBSPY_AVAILABLE else "JobSpy not installed"
    }


# Create FunctionTools
search_jobs_tool = FunctionTool(func=search_jobs_with_jobspy)
check_jobspy_tool = FunctionTool(func=check_jobspy_status)

# Export list
jobspy_tools = [search_jobs_tool, check_jobspy_tool]
