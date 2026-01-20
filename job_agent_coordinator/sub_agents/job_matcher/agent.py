"""Job Matcher sub-agent: Analyzes job descriptions against user profiles."""

import os
import logging
import re
import hashlib
import requests
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from .prompt import JOB_MATCHER_PROMPT
from job_agent_coordinator.tools.profile_store import get_store
from job_agent_coordinator.tools.job_cache import get_cache

logger = logging.getLogger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "ollama/gemma3:27b")
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _fetch_job_description(url: str) -> Optional[str]:
    """
    Fetch and extract job description from a URL.
    Returns cleaned text content or None if fetch fails.
    
    Note: Some sites (Indeed, Greenhouse, Lever) require JS rendering.
    This function uses basic requests which may return minimal content for JS-heavy sites.
    """
    if not url:
        return None
    
    # Check if URL needs JS (will get minimal content)
    js_sites = ["greenhouse.io", "lever.co", "indeed.com", "linkedin.com", "workday.com"]
    needs_js = any(site in url.lower() for site in js_sites)
    
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove non-content elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
            element.decompose()
        
        # Try to find job description container (extended selectors)
        job_selectors = [
            # Greenhouse specific
            "#content", ".content", "[class*='content']",
            # Generic job description
            ".job-description", "#job-description", "[class*='job-desc']",
            ".description", "#description", "[class*='Description']",
            ".job-details", "#job-details", "[class*='jobDetails']",
            ".posting-content", "[class*='posting']",
            # Indeed specific
            "#jobDescriptionText", ".jobsearch-JobComponent",
            # LinkedIn
            ".description__text", ".show-more-less-html",
            # Fallbacks
            "article", "main", "[role='main']", ".container",
        ]
        
        job_content = None
        for selector in job_selectors:
            try:
                container = soup.select_one(selector)
                if container:
                    text = container.get_text(separator=" ", strip=True)
                    if len(text) > 200:  # Minimum viable content
                        job_content = text
                        break
            except:
                continue
        
        if not job_content:
            # Fallback to body text
            body = soup.find("body")
            if body:
                job_content = body.get_text(separator=" ", strip=True)
            else:
                job_content = soup.get_text(separator=" ", strip=True)
        
        # Clean up
        job_content = re.sub(r'\s+', ' ', job_content)
        
        # Truncate if too long
        if len(job_content) > 10000:
            job_content = job_content[:10000]
        
        if needs_js and len(job_content) < 500:
            logger.info(f"📄 Fetched {len(job_content)} chars (site requires JS, may be incomplete)")
        else:
            logger.info(f"📄 Fetched {len(job_content)} chars from {url[:50]}...")
        
        return job_content if len(job_content) >= 100 else None
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            logger.warning(f"⚠️ Site blocked request (403): {url[:50]}...")
        else:
            logger.warning(f"⚠️ HTTP error fetching description: {e}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch job description: {e}")
        return None


def _get_profile_context() -> Dict[str, Any]:
    """Get profile context as a dictionary for internal use."""
    return get_store().get_search_context()


def _get_profile_hash() -> str:
    """Generate a hash of the current profile for cache invalidation."""
    context = _get_profile_context()
    if not context:
        return ""
    profile_str = str(sorted(context.items()))
    return hashlib.md5(profile_str.encode()).hexdigest()[:8]


def _generate_job_id(job_title: str, company: str, location: str, job_url: str) -> str:
    """Generate a consistent job ID for matching (must match job_cache._generate_id)."""
    if job_url:
        return hashlib.md5(job_url.encode()).hexdigest()[:12]
    # Fallback must match job_cache: title + company + location
    content = f"{job_title}{company}{location}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def analyze_job_match(
    job_title: str,
    company: str,
    job_description: str,
    location: str = "",
    salary_info: str = "",
    job_url: str = "",
    job_id: str = "",
    use_cache: bool = True,
    fetch_description: bool = True
) -> Dict[str, Any]:
    """
    Analyze how well a job matches the user's profile.
    
    Args:
        job_title: The job title
        company: Company name
        job_description: Full job description text
        location: Job location
        salary_info: Salary range if available
        job_url: Link to job posting
        job_id: Optional job ID (use when matching from cache to ensure ID consistency)
        use_cache: Whether to check/use cached results (default: True)
        fetch_description: If description is empty and URL exists, fetch it (default: True)
    
    Returns:
        Detailed match analysis with scores and recommendations
    """
    # Use provided job_id or generate one
    if not job_id:
        job_id = _generate_job_id(job_title, company, location, job_url)
    profile_hash = _get_profile_hash()
    
    # Fetch job description if missing but URL is available
    if (not job_description or len(job_description) < 50) and job_url and fetch_description:
        logger.info(f"📥 Fetching description for: {job_title[:40]}...")
        fetched_desc = _fetch_job_description(job_url)
        if fetched_desc:
            job_description = fetched_desc
    
    # Check cache first
    if use_cache:
        cache = get_cache()
        cached = cache.get_match(job_id, profile_hash)
        if cached:
            logger.info(f"🎯 Cache hit: {job_title[:30]} score={cached.get('match_score', 0)}%")
            return {
                "success": True,
                "from_cache": True,
                "match_score": cached.get("match_score", 0),
                "match_level": cached.get("match_level", "unknown"),
                "toon_report": cached.get("toon_report", ""),
            }
    
    # Get user's profile context
    profile = _get_profile_context()
    if not profile:
        return {
            "success": False,
            "error": "No user profile found. Please create a profile first using create_profile.",
            "match_score": 0
        }
    
    # Extract profile info
    user_skills = set(s.lower() for s in profile.get("skills", []))
    target_roles = [r.lower() for r in profile.get("target_roles", [])]
    target_locations = [l.lower() for l in profile.get("target_locations", [])]
    excluded_companies = [c.lower() for c in profile.get("excluded_companies", [])]
    remote_pref = profile.get("remote_preference", "hybrid")
    salary_range = profile.get("salary_range")
    
    # Check for excluded company
    if company.lower() in excluded_companies:
        return {
            "success": True,
            "match_score": 0,
            "match_level": "excluded",
            "job_title": job_title,
            "company": company,
            "warning": f"⚠️ {company} is in your excluded companies list",
            "recommendation": "This company is on your exclusion list. Consider if you want to proceed."
        }
    
    # Analyze job description for required skills
    job_desc_lower = job_description.lower()
    
    # Common tech skills to look for
    tech_skills = [
        "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#",
        "react", "angular", "vue", "node", "django", "flask", "fastapi", "spring",
        "aws", "azure", "gcp", "google cloud", "kubernetes", "docker", "terraform",
        "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "machine learning", "ml", "ai", "artificial intelligence", "deep learning",
        "data science", "data engineering", "analytics", "etl", "spark", "kafka",
        "agile", "scrum", "devops", "ci/cd", "git", "linux",
        "api", "rest", "graphql", "microservices", "distributed systems",
    ]
    
    # Find skills mentioned in job
    job_skills_found = set()
    for skill in tech_skills:
        if skill in job_desc_lower:
            job_skills_found.add(skill)
    
    # Calculate skill match
    matching_skills = user_skills.intersection(job_skills_found)
    missing_skills = job_skills_found - user_skills
    extra_skills = user_skills - job_skills_found
    
    skill_match_pct = (len(matching_skills) / max(len(job_skills_found), 1)) * 100 if job_skills_found else 50
    
    # Role match
    role_match = any(role in job_title.lower() for role in target_roles) if target_roles else True
    role_score = 100 if role_match else 60
    
    # Location match
    location_lower = location.lower() if location else ""
    remote_in_job = "remote" in job_desc_lower or "remote" in location_lower
    location_match = (
        any(loc in location_lower for loc in target_locations) or
        ("remote" in target_locations and remote_in_job) or
        not target_locations
    )
    location_score = 100 if location_match else 50
    
    # Remote preference match
    if remote_pref == "remote" and not remote_in_job:
        location_score -= 20
    elif remote_pref == "onsite" and remote_in_job:
        location_score -= 10  # Not as penalizing since remote is flexible
    
    # Calculate overall score
    overall_score = int(
        (skill_match_pct * 0.5) +  # Skills are 50% of score
        (role_score * 0.3) +        # Role match is 30%
        (location_score * 0.2)      # Location is 20%
    )
    
    # Determine match level
    if overall_score >= 80:
        match_level = "strong"
        match_emoji = "🟢"
        match_text = "Strong Match"
    elif overall_score >= 60:
        match_level = "good"
        match_emoji = "🟢"
        match_text = "Good Match"
    elif overall_score >= 40:
        match_level = "partial"
        match_emoji = "🟡"
        match_text = "Partial Match"
    else:
        match_level = "weak"
        match_emoji = "🔴"
        match_text = "Weak Match"
    
    # Experience level detection
    exp_patterns = {
        "entry": r"(entry.?level|0-2 years|junior|new grad|associate)",
        "mid": r"(mid.?level|3-5 years|intermediate|2-4 years|3-6 years)",
        "senior": r"(senior|5\+ years|7\+ years|lead|principal|staff|8\+ years|10\+ years)"
    }
    
    detected_level = "mid"  # default
    for level, pattern in exp_patterns.items():
        if re.search(pattern, job_desc_lower):
            detected_level = level
            break
    
    # Generate TOON formatted report
    toon_report = _generate_toon_report(
        job_title=job_title,
        company=company,
        location=location,
        salary_info=salary_info,
        job_url=job_url,
        overall_score=overall_score,
        match_level=match_level,
        matching_skills=matching_skills,
        missing_skills=missing_skills,
        extra_skills=extra_skills,
        role_match=role_match,
        location_match=location_match,
        remote_in_job=remote_in_job,
        remote_pref=remote_pref,
        salary_range=salary_range,
        profile=profile,
        detected_level=detected_level,
    )
    
    result = {
        "success": True,
        "match_score": overall_score,
        "match_level": match_level,
        "toon_report": toon_report,
    }
    
    # Cache the result
    if use_cache:
        cache = get_cache()
        cache.add_match(job_id, result, profile_hash)
        logger.info(f"🎯 Cached match: {job_title[:30]} score={overall_score}%")
    
    return result


def _generate_recommendations(
    matching: set, missing: set, extra: set,
    role_match: bool, loc_match: bool, score: int
) -> List[str]:
    """Generate actionable recommendations."""
    recs = []
    
    if score >= 80:
        recs.append("Strong candidate - apply with confidence")
        if matching:
            recs.append(f"Highlight these matching skills prominently: {', '.join(list(matching)[:5])}")
    elif score >= 60:
        recs.append("Good fit - emphasize your strengths in the application")
        if missing:
            recs.append(f"Consider addressing these gaps: {', '.join(list(missing)[:3])}")
    else:
        recs.append("Consider if this role aligns with your goals")
        if missing:
            recs.append(f"Significant skill gaps to address: {', '.join(list(missing)[:5])}")
    
    if extra:
        recs.append(f"You have additional relevant skills not listed: {', '.join(list(extra)[:3])}")
    
    if not role_match:
        recs.append("Job title differs from your targets - ensure responsibilities align")
    
    if not loc_match:
        recs.append("Location may not match preferences - verify remote/relocation options")
    
    return recs


def _generate_toon_report(
    job_title: str,
    company: str,
    location: str,
    salary_info: str,
    job_url: str,
    overall_score: int,
    match_level: str,
    matching_skills: set,
    missing_skills: set,
    extra_skills: set,
    role_match: bool,
    location_match: bool,
    remote_in_job: bool,
    remote_pref: str,
    salary_range: str,
    profile: Dict[str, Any],
    detected_level: str,
) -> str:
    """Generate a TOON formatted report."""
    lines = []
    
    # Header
    lines.append(f"[job_match_report]")
    lines.append(f"job: {job_title} @ {company}")
    lines.append(f"score: {overall_score}%")
    lines.append(f"level: {match_level}")
    if job_url:
        lines.append(f"url: {job_url}")
    if location:
        lines.append(f"location: {location}")
    if salary_info:
        lines.append(f"salary: {salary_info}")
    lines.append(f"experience_level: {detected_level}")
    lines.append("")
    
    # Assessment
    lines.append("[assessment]")
    if overall_score >= 80:
        lines.append(f"Strong match for {job_title}. Your profile aligns well with requirements.")
    elif overall_score >= 60:
        lines.append(f"Good potential match. Some skill gaps to address but solid foundation.")
    elif overall_score >= 40:
        lines.append(f"Partial match. Consider if this role aligns with your career goals.")
    else:
        lines.append(f"Significant gaps between profile and requirements. Carefully evaluate fit.")
    lines.append("")
    
    # Matching Skills
    lines.append("[matching_skills]")
    if matching_skills:
        for skill in list(matching_skills)[:8]:
            lines.append(f"- {skill}: demonstrated in profile")
    else:
        lines.append("- none identified")
    lines.append("")
    
    # Skill Gaps
    lines.append("[skill_gaps]")
    if missing_skills:
        for skill in list(missing_skills)[:6]:
            lines.append(f"- {skill}: consider learning or highlighting related experience")
    else:
        lines.append("- none: profile covers requirements")
    lines.append("")
    
    # Compensation
    lines.append("[compensation]")
    lines.append(f"job_range: {salary_info if salary_info else 'Not disclosed'}")
    lines.append(f"profile_target: {salary_range if salary_range else 'Not set'}")
    lines.append(f"alignment: {'unknown' if not salary_info else 'check manually'}")
    lines.append("")
    
    # Location
    lines.append("[location]")
    lines.append(f"job_location: {location if location else 'Not specified'}")
    lines.append(f"profile_preference: {remote_pref}")
    lines.append(f"remote_option: {'yes' if remote_in_job else 'no'}")
    loc_compat = "yes" if location_match else ("partial" if remote_in_job else "no")
    lines.append(f"compatible: {loc_compat}")
    lines.append("")
    
    # Recommendations
    recs = _generate_recommendations(
        matching_skills, missing_skills, extra_skills,
        role_match, location_match, overall_score
    )
    lines.append("[recommendations]")
    for i, rec in enumerate(recs[:5], 1):
        lines.append(f"{i}. {rec}")
    lines.append("")
    
    # Cover Letter Points
    lines.append("[cover_letter_points]")
    if matching_skills:
        top_skills = list(matching_skills)[:3]
        lines.append(f"lead_with: {top_skills[0] if top_skills else 'relevant experience'}")
        lines.append(f"emphasize: {', '.join(top_skills)}")
    else:
        lines.append(f"lead_with: transferable skills and enthusiasm")
        lines.append(f"emphasize: learning ability and adaptability")
    if missing_skills:
        lines.append(f"address: willingness to learn {list(missing_skills)[0]}")
    lines.append("")
    
    # Extra Skills
    lines.append("[extra_skills]")
    if extra_skills:
        for skill in list(extra_skills)[:5]:
            lines.append(f"- {skill}")
    else:
        lines.append("- none: all skills align with job requirements")
    
    return "\n".join(lines)


# Create the tool
analyze_job_match_tool = FunctionTool(func=analyze_job_match)

# Note: job_matcher_agent is deprecated - use analyze_job_match_tool directly for faster matching
# The agent is kept for backwards compatibility but the tool is preferred
job_matcher_agent = LlmAgent(
    name="job_matcher_agent",
    model=LLM_MODEL,
    description=(
        "Analyzes job descriptions against user profiles to determine compatibility. "
        "Provides detailed match reports with scores, skill analysis, and recommendations."
    ),
    instruction=JOB_MATCHER_PROMPT,
    output_key="job_match_report",
    tools=[
        analyze_job_match_tool,
    ],
)

logger.info(f"🎯 Job Matcher Agent initialized (model={LLM_MODEL})")
