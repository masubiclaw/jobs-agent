"""Cache tools for inline caching of agent responses and search results."""

import json
import logging
import re
from typing import Any, Optional

from google.adk.tools import FunctionTool

from ..sub_agents.history_manager.vector_store import get_vector_store

logger = logging.getLogger(__name__)

# =============================================================================
# Inline Cache Functions - Called by agents to cache results immediately
# =============================================================================

def cache_job_result(
    title: str,
    company: str,
    url: str,
    platform: str,
    location: str = "",
    posted_date: str = "",
    salary: str = "",
    description_snippet: str = ""
) -> dict:
    """
    Cache a single job result immediately when found.
    
    Args:
        title: Job title
        company: Company name
        url: Source URL (REQUIRED)
        platform: Where found (linkedin, indeed, glassdoor)
        location: Job location
        posted_date: When posted
        salary: Salary info
        description_snippet: Brief description
    
    Returns:
        Cache confirmation with job ID
    """
    store = get_vector_store()
    
    # Generate a simple cache key
    cache_key = f"{platform}:{company}:{title}".lower().replace(" ", "_")[:64]
    
    job_data = {
        "title": title,
        "company": company,
        "url": url,
        "platform": platform,
        "location": location,
        "posted_date": posted_date,
        "salary": salary,
        "description_snippet": description_snippet[:500] if description_snippet else ""
    }
    
    # Store as a cached response
    store.set_cached_response(
        cache_type="job_result",
        query=f"{title} at {company}",
        response=json.dumps(job_data),
        sources=[{"url": url, "platform": platform, "title": title}],
        company=company,
        role=title
    )
    
    logger.info(f"📦 CACHED JOB: {title} @ {company} [{platform}]")
    logger.info(f"   🔗 URL: {url}")
    
    return {
        "cached": True,
        "job": job_data,
        "message": f"Cached job: {title} at {company}"
    }


def cache_job_analysis(
    job_title: str,
    company: str,
    analysis: str,
    match_score: int = 0,
    skills_required: str = "",
    red_flags: str = "",
    recommendation: str = "",
    source_url: str = ""
) -> dict:
    """
    Cache a job analysis result immediately.
    
    Args:
        job_title: Job title analyzed
        company: Company name
        analysis: Full analysis text
        match_score: Match score 0-100
        skills_required: Comma-separated required skills
        red_flags: Any red flags found
        recommendation: Apply/Skip/Needs More Info
        source_url: Original job posting URL
    
    Returns:
        Cache confirmation
    """
    store = get_vector_store()
    
    analysis_data = {
        "job_title": job_title,
        "company": company,
        "analysis": analysis,
        "match_score": match_score,
        "skills_required": skills_required,
        "red_flags": red_flags,
        "recommendation": recommendation,
        "source_url": source_url
    }
    
    cache_key = store.set_cached_response(
        cache_type="job_analysis",
        query=f"Analysis of {job_title} at {company}",
        response=json.dumps(analysis_data),
        sources=[{"url": source_url, "title": job_title, "platform": "analysis"}] if source_url else [],
        company=company,
        role=job_title
    )
    
    logger.info(f"📊 CACHED JOB ANALYSIS: {job_title} @ {company}")
    logger.info(f"   Score: {match_score}/100 | Recommendation: {recommendation}")
    if source_url:
        logger.info(f"   🔗 Source: {source_url}")
    
    return {
        "cached": True,
        "cache_key": cache_key,
        "analysis": analysis_data,
        "message": f"Cached analysis for {job_title} at {company}"
    }


def cache_company_analysis(
    company: str,
    analysis: str,
    rating: float = 0.0,
    culture_summary: str = "",
    values: str = "",
    pros: str = "",
    cons: str = "",
    recommend: str = "",
    glassdoor_url: str = ""
) -> dict:
    """
    Cache a company analysis result immediately.
    
    Args:
        company: Company name
        analysis: Full analysis text
        rating: Glassdoor rating (0-5)
        culture_summary: Brief culture description
        values: Company values
        pros: Key pros from reviews
        cons: Key cons from reviews
        recommend: Yes/Maybe/No
        glassdoor_url: Glassdoor company page URL
    
    Returns:
        Cache confirmation
    """
    store = get_vector_store()
    
    company_data = {
        "company": company,
        "analysis": analysis,
        "rating": rating,
        "culture_summary": culture_summary,
        "values": values,
        "pros": pros,
        "cons": cons,
        "recommend": recommend,
        "glassdoor_url": glassdoor_url
    }
    
    cache_key = store.set_cached_response(
        cache_type="company_analysis",
        query=f"Analysis of {company}",
        response=json.dumps(company_data),
        sources=[{"url": glassdoor_url, "title": company, "platform": "glassdoor"}] if glassdoor_url else [],
        company=company
    )
    
    logger.info(f"🏢 CACHED COMPANY ANALYSIS: {company}")
    logger.info(f"   Rating: {rating}/5 | Recommend: {recommend}")
    if glassdoor_url:
        logger.info(f"   🔗 Glassdoor: {glassdoor_url}")
    
    return {
        "cached": True,
        "cache_key": cache_key,
        "company_data": company_data,
        "message": f"Cached company analysis for {company}"
    }


def get_cached_job(
    title: str,
    company: str,
    platform: str = ""
) -> dict:
    """
    Check if a job is already cached.
    
    Args:
        title: Job title
        company: Company name
        platform: Platform (optional filter)
    
    Returns:
        Cached job data or {"cached": False}
    """
    store = get_vector_store()
    
    result = store.get_cached_response(
        cache_type="job_result",
        query=f"{title} at {company}",
        company=company,
        role=title
    )
    
    if result and result.get("cached"):
        logger.info(f"✅ CACHE HIT - Job: {title} @ {company}")
        try:
            job_data = json.loads(result.get("response", "{}"))
            return {
                "cached": True,
                "job": job_data,
                "timestamp": result.get("timestamp")
            }
        except:
            pass
    
    logger.debug(f"❌ CACHE MISS - Job: {title} @ {company}")
    return {"cached": False}


def get_cached_job_analysis(
    job_title: str,
    company: str
) -> dict:
    """
    Check if a job analysis is already cached.
    
    Args:
        job_title: Job title
        company: Company name
    
    Returns:
        Cached analysis or {"cached": False}
    """
    store = get_vector_store()
    
    result = store.get_cached_response(
        cache_type="job_analysis",
        query=f"Analysis of {job_title} at {company}",
        company=company,
        role=job_title
    )
    
    if result and result.get("cached"):
        logger.info(f"✅ CACHE HIT - Analysis: {job_title} @ {company}")
        try:
            analysis_data = json.loads(result.get("response", "{}"))
            return {
                "cached": True,
                "analysis": analysis_data,
                "timestamp": result.get("timestamp")
            }
        except:
            pass
    
    logger.debug(f"❌ CACHE MISS - Analysis: {job_title} @ {company}")
    return {"cached": False}


def get_cached_company_analysis(
    company: str
) -> dict:
    """
    Check if a company analysis is already cached.
    
    Args:
        company: Company name
    
    Returns:
        Cached company analysis or {"cached": False}
    """
    store = get_vector_store()
    
    result = store.get_cached_response(
        cache_type="company_analysis",
        query=f"Analysis of {company}",
        company=company
    )
    
    if result and result.get("cached"):
        logger.info(f"✅ CACHE HIT - Company: {company}")
        try:
            company_data = json.loads(result.get("response", "{}"))
            return {
                "cached": True,
                "company_data": company_data,
                "timestamp": result.get("timestamp")
            }
        except:
            pass
    
    logger.debug(f"❌ CACHE MISS - Company: {company}")
    return {"cached": False}


def list_cached_jobs(limit: int = 20) -> dict:
    """
    List all cached job results.
    
    Args:
        limit: Maximum number of jobs to return
    
    Returns:
        List of cached jobs
    """
    store = get_vector_store()
    
    if not store.client:
        return {"jobs": [], "message": "ChromaDB not available"}
    
    try:
        results = store.response_cache.get(
            where={"cache_type": "job_result"},
            include=["documents", "metadatas"],
            limit=limit
        )
        
        jobs = []
        if results and results.get("ids"):
            for i, cache_id in enumerate(results["ids"]):
                try:
                    doc = results["documents"][i] if results.get("documents") else "{}"
                    job_data = json.loads(doc)
                    jobs.append(job_data)
                except:
                    pass
        
        logger.info(f"📋 Listed {len(jobs)} cached jobs")
        return {
            "count": len(jobs),
            "jobs": jobs
        }
    except Exception as e:
        logger.error(f"Error listing cached jobs: {e}")
        return {"jobs": [], "error": str(e)}


# =============================================================================
# Create FunctionTools for agents to use
# =============================================================================

cache_job_result_tool = FunctionTool(func=cache_job_result)
cache_job_analysis_tool = FunctionTool(func=cache_job_analysis)
cache_company_analysis_tool = FunctionTool(func=cache_company_analysis)
get_cached_job_tool = FunctionTool(func=get_cached_job)
get_cached_job_analysis_tool = FunctionTool(func=get_cached_job_analysis)
get_cached_company_analysis_tool = FunctionTool(func=get_cached_company_analysis)
list_cached_jobs_tool = FunctionTool(func=list_cached_jobs)

# List of all cache tools for easy import
cache_tools = [
    cache_job_result_tool,
    cache_job_analysis_tool,
    cache_company_analysis_tool,
    get_cached_job_tool,
    get_cached_job_analysis_tool,
    get_cached_company_analysis_tool,
    list_cached_jobs_tool,
]
