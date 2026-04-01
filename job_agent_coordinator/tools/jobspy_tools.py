"""JobSpy tools for job scraping from LinkedIn, Indeed, Glassdoor, ZipRecruiter."""

import logging
import time

try:
    from google.adk.tools import FunctionTool
except ImportError:
    FunctionTool = lambda func: func

logger = logging.getLogger(__name__)

try:
    from jobspy import scrape_jobs
    JOBSPY_AVAILABLE = True
except ImportError:
    JOBSPY_AVAILABLE = False
    logger.warning("JobSpy not installed: pip install python-jobspy")


def search_jobs_with_jobspy(
    search_term: str,
    location: str,
    results_wanted: int = 15,
    hours_old: int = 24,
    sites: str = "indeed,linkedin",
    exclude_companies: str = ""
) -> dict:
    """Search for jobs using JobSpy.
    
    Args:
        search_term: Job title or keywords to search
        location: City, state, or "Remote"
        results_wanted: Number of results to return
        hours_old: Max age of job postings in hours (default 24 = 1 day for fresh links)
        sites: Comma-separated list of sites to search
        exclude_companies: Comma-separated companies to exclude
    """
    if not JOBSPY_AVAILABLE:
        return {"success": False, "error": "JobSpy not installed", "jobs": []}
    
    start = time.time()
    site_list = [s.strip() for s in sites.split(",") if s.strip() in ["indeed", "linkedin", "glassdoor", "zip_recruiter"]] or ["indeed", "linkedin"]
    exclusions = [c.strip().lower() for c in exclude_companies.split(",") if c.strip()]
    
    logger.info(f"🔍 JobSpy: '{search_term}' in {location} (sites={','.join(site_list)}, excl={exclusions or 'none'})")
    
    try:
        jobs_df = scrape_jobs(
            site_name=site_list,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted * 2 if exclusions else results_wanted,
            hours_old=hours_old,
            country_indeed="USA"
        )
        
        # Filter exclusions
        if exclusions:
            before = len(jobs_df)
            jobs_df = jobs_df[~jobs_df['company'].apply(
                lambda c: any(e in str(c).lower() for e in exclusions) if c else False
            )]
            logger.info(f"   Filtered {before}→{len(jobs_df)} (excluded {before - len(jobs_df)})")
        
        # Convert to list
        jobs = []
        for _, row in jobs_df.iterrows():
            salary = "Not disclosed"
            try:
                min_a, max_a = row.get('min_amount'), row.get('max_amount')
                if min_a and max_a and not (str(min_a) == 'nan' or str(max_a) == 'nan'):
                    import math
                    if not math.isnan(float(min_a)) and not math.isnan(float(max_a)):
                        salary = f"${int(min_a):,} - ${int(max_a):,}"
            except:
                pass
            
            jobs.append({
                "title": row.get('title', 'Unknown'),
                "company": row.get('company', 'Unknown'),
                "location": row.get('location', 'Unknown'),
                "url": row.get('job_url', ''),
                "platform": row.get('site', 'unknown'),
                "posted_date": str(row.get('date_posted', '')) if row.get('date_posted') else None,
                "salary": salary,
            })
        
        jobs = jobs[:results_wanted]
        elapsed = time.time() - start
        logger.info(f"✅ Found {len(jobs)} jobs in {elapsed:.1f}s")
        
        # Auto-cache jobs
        try:
            from .job_cache import get_cache
            cache = get_cache()
            cached = cache.add_many(jobs, search_term=search_term, location=location)
            if cached > 0:
                logger.info(f"💾 Auto-cached {cached} new jobs")
        except Exception as e:
            logger.debug(f"Auto-cache failed: {e}")
        
        return {"success": True, "count": len(jobs), "search_term": search_term, "location": location, "jobs": jobs}
        
    except Exception as e:
        logger.error(f"❌ JobSpy error: {e}")
        return {"success": False, "error": str(e), "jobs": []}


search_jobs_tool = FunctionTool(func=search_jobs_with_jobspy)
