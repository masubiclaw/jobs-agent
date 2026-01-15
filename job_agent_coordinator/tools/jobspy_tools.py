"""JobSpy tools for direct job scraping from LinkedIn, Indeed, Glassdoor, ZipRecruiter."""

import logging
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

# Job search statistics
_jobspy_stats = {
    "total_searches": 0,
    "total_jobs_found": 0,
    "total_jobs_excluded": 0,
    "total_time_seconds": 0.0,
    "searches_by_location": {},
    "errors": 0,
}


def get_jobspy_stats() -> dict:
    """Get JobSpy search statistics."""
    return _jobspy_stats.copy()


def reset_jobspy_stats():
    """Reset JobSpy statistics."""
    global _jobspy_stats
    _jobspy_stats = {
        "total_searches": 0,
        "total_jobs_found": 0,
        "total_jobs_excluded": 0,
        "total_time_seconds": 0.0,
        "searches_by_location": {},
        "errors": 0,
    }

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
    sites: str = "indeed,linkedin",
    exclude_companies: str = ""
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
        exclude_companies: Comma-separated company names to exclude (e.g., "amazon,google,meta")
    
    Returns:
        Dict with jobs list and metadata
    """
    global _jobspy_stats
    start_time = time.time()
    
    if not JOBSPY_AVAILABLE:
        _jobspy_stats["errors"] += 1
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
        
        # Parse exclusions
        exclusion_list = [c.strip().lower() for c in exclude_companies.split(",") if c.strip()]
        
        # Detailed logging
        logger.info("")
        logger.info("=" * 70)
        logger.info("🔍 JOBSPY JOB SEARCH")
        logger.info("=" * 70)
        logger.info(f"   Search Term: '{search_term}'")
        logger.info(f"   Location: {location}")
        logger.info(f"   Sites: {', '.join(site_list)}")
        logger.info(f"   Max Results: {results_wanted}")
        logger.info(f"   Hours Old: {hours_old} (last {hours_old // 24} days)")
        if exclusion_list:
            logger.info(f"   🚫 Excluding Companies: {', '.join(exclusion_list)}")
        
        # Scrape jobs (fetch extra if excluding companies)
        fetch_count = results_wanted * 2 if exclusion_list else results_wanted
        
        jobs_df = scrape_jobs(
            site_name=site_list,
            search_term=search_term,
            location=location,
            results_wanted=fetch_count,
            hours_old=hours_old,
            country_indeed="USA"
        )
        
        raw_count = len(jobs_df)
        scrape_time = time.time() - start_time
        
        logger.info(f"   ⏱️  Scrape Time: {scrape_time:.2f}s")
        logger.info(f"   📊 Raw Results: {raw_count} jobs")
        
        # Log platform breakdown
        if raw_count > 0 and 'site' in jobs_df.columns:
            platform_counts = jobs_df['site'].value_counts().to_dict()
            logger.info(f"   📈 By Platform: {platform_counts}")
        
        # Filter out excluded companies
        excluded_count = 0
        if exclusion_list:
            def should_exclude(company):
                if not company:
                    return False
                company_lower = str(company).lower()
                return any(exc in company_lower for exc in exclusion_list)
            
            before_filter = len(jobs_df)
            jobs_df = jobs_df[~jobs_df['company'].apply(should_exclude)]
            excluded_count = before_filter - len(jobs_df)
            logger.info(f"   🚫 Excluded: {excluded_count} jobs from blocked companies")
            logger.info(f"   ✅ After Filter: {len(jobs_df)} jobs")
        
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
        
        # Cap results to requested amount
        jobs = jobs[:results_wanted]
        
        # Calculate final stats
        total_time = time.time() - start_time
        
        # Update global stats
        _jobspy_stats["total_searches"] += 1
        _jobspy_stats["total_jobs_found"] += len(jobs)
        _jobspy_stats["total_jobs_excluded"] += excluded_count
        _jobspy_stats["total_time_seconds"] += total_time
        if location not in _jobspy_stats["searches_by_location"]:
            _jobspy_stats["searches_by_location"][location] = 0
        _jobspy_stats["searches_by_location"][location] += 1
        
        # Log summary
        logger.info("")
        logger.info("-" * 70)
        logger.info("📋 SEARCH RESULTS SUMMARY")
        logger.info("-" * 70)
        logger.info(f"   ✅ Total Jobs Returned: {len(jobs)}")
        logger.info(f"   ⏱️  Total Time: {total_time:.2f}s")
        logger.info(f"   📊 Raw → Filtered → Final: {raw_count} → {raw_count - excluded_count} → {len(jobs)}")
        
        # Log unique companies found
        companies = set(j["company"] for j in jobs if j.get("company"))
        logger.info(f"   🏢 Unique Companies: {len(companies)}")
        if len(companies) <= 10:
            logger.info(f"      {', '.join(sorted(companies))}")
        
        # Log salary stats
        jobs_with_salary = [j for j in jobs if j.get("salary") and j["salary"] != "Not disclosed"]
        logger.info(f"   💰 Jobs with Salary Info: {len(jobs_with_salary)}/{len(jobs)}")
        
        # Log session stats
        logger.info(f"   📈 Session Stats: {_jobspy_stats['total_searches']} searches, "
                   f"{_jobspy_stats['total_jobs_found']} jobs found, "
                   f"{_jobspy_stats['total_time_seconds']:.1f}s total")
        logger.info("=" * 70)
        logger.info("")
        
        return {
            "success": True,
            "count": len(jobs),
            "search_term": search_term,
            "location": location,
            "sites_searched": site_list,
            "excluded_companies": exclusion_list if exclusion_list else [],
            "raw_results": raw_count,
            "excluded_count": excluded_count,
            "unique_companies": len(companies),
            "jobs_with_salary": len(jobs_with_salary),
            "search_time_seconds": total_time,
            "jobs": jobs
        }
        
    except Exception as e:
        total_time = time.time() - start_time
        _jobspy_stats["errors"] += 1
        logger.error(f"❌ JobSpy error after {total_time:.2f}s: {e}")
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
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


def scrape_job_details(job_url: str) -> dict:
    """
    Scrape full job details from a job posting URL.
    
    Works with LinkedIn, Indeed, and most job board URLs.
    Returns the full job description, requirements, and any other details.
    
    Args:
        job_url: The URL of the job posting to scrape
    
    Returns:
        Dict with scraped job details
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        logger.info(f"🔍 Scraping job details from: {job_url}")
        
        resp = requests.get(job_url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        result = {
            "url": job_url,
            "success": True,
            "title": None,
            "company": None,
            "location": None,
            "description": None,
            "requirements": None,
            "salary": None,
            "benefits": None,
            "raw_text": None
        }
        
        # LinkedIn job pages
        if 'linkedin.com' in job_url:
            # Title
            title_el = soup.find('h1', class_='top-card-layout__title')
            if title_el:
                result["title"] = title_el.get_text(strip=True)
            
            # Company
            company_el = soup.find('a', class_='topcard__org-name-link')
            if company_el:
                result["company"] = company_el.get_text(strip=True)
            
            # Location
            location_el = soup.find('span', class_='topcard__flavor--bullet')
            if location_el:
                result["location"] = location_el.get_text(strip=True)
            
            # Description
            desc_el = soup.find('div', class_='description__text')
            if desc_el:
                result["description"] = desc_el.get_text(separator='\n', strip=True)
        
        # Indeed job pages
        elif 'indeed.com' in job_url:
            # Title
            title_el = soup.find('h1', {'data-testid': 'jobsearch-JobInfoHeader-title'})
            if title_el:
                result["title"] = title_el.get_text(strip=True)
            
            # Company
            company_el = soup.find('div', {'data-testid': 'inlineHeader-companyName'})
            if company_el:
                result["company"] = company_el.get_text(strip=True)
            
            # Description
            desc_el = soup.find('div', id='jobDescriptionText')
            if desc_el:
                result["description"] = desc_el.get_text(separator='\n', strip=True)
        
        # Generic fallback - extract all text from main content areas
        else:
            # Try common job description containers
            for selector in ['article', 'main', '.job-description', '#job-description', '.description']:
                el = soup.select_one(selector)
                if el:
                    result["description"] = el.get_text(separator='\n', strip=True)[:5000]
                    break
        
        # Get raw text as fallback
        if not result["description"]:
            body = soup.find('body')
            if body:
                result["raw_text"] = body.get_text(separator='\n', strip=True)[:5000]
        
        logger.info(f"✅ Scraped job: {result.get('title', 'Unknown')}")
        if result["description"]:
            logger.info(f"   Description length: {len(result['description'])} chars")
        
        return result
        
    except requests.RequestException as e:
        logger.error(f"❌ Failed to scrape {job_url}: {e}")
        return {
            "url": job_url,
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"❌ Error parsing {job_url}: {e}")
        return {
            "url": job_url,
            "success": False,
            "error": str(e)
        }


# Create FunctionTools
search_jobs_tool = FunctionTool(func=search_jobs_with_jobspy)
check_jobspy_tool = FunctionTool(func=check_jobspy_status)
scrape_job_tool = FunctionTool(func=scrape_job_details)

# Export list
jobspy_tools = [search_jobs_tool, check_jobspy_tool, scrape_job_tool]
