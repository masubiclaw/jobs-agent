"""
Job Matcher: Two-pass job matching with keyword analysis and LLM holistic review.

Pass 1: Fast keyword/regex matching (~0.01s/job)
  - Skill intersection analysis
  - Role title matching
  - Location/remote preference check

Pass 2: LLM holistic analysis (~3-5s/job)
  - Deep contextual understanding
  - Experience alignment
  - Culture fit signals
  - Detailed recommendations

Both passes return scores that can be combined or used independently.
Includes checkpoint/resume support for long-running batch jobs.
"""

import os
import logging
import re
import hashlib
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from .prompt import JOB_MATCHER_PROMPT
from job_agent_coordinator.tools.profile_store import get_store
from job_agent_coordinator.tools.job_cache import get_cache

logger = logging.getLogger(__name__)

# Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "ollama/gemma3:27b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "gemma3:12b")
REQUEST_TIMEOUT = 15
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 120))

# MLX-LM Configuration (optional fine-tuned model)
MLX_MODEL_PATH = os.getenv("MLX_MODEL_PATH", "")  # Path to fine-tuned MLX model
USE_MLX_MODEL = os.getenv("USE_MLX_MODEL", "false").lower() == "true"

# Lazy-loaded MLX model
_mlx_model = None
_mlx_tokenizer = None
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
CHECKPOINT_DIR = Path(".job_cache")

# Common tech skills for keyword matching
TECH_SKILLS = [
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#",
    "react", "angular", "vue", "node", "django", "flask", "fastapi", "spring",
    "aws", "azure", "gcp", "google cloud", "kubernetes", "docker", "terraform",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "machine learning", "ml", "ai", "artificial intelligence", "deep learning",
    "data science", "data engineering", "analytics", "etl", "spark", "kafka",
    "agile", "scrum", "devops", "ci/cd", "git", "linux",
    "api", "rest", "graphql", "microservices", "distributed systems",
    "scala", "ruby", "php", "swift", "kotlin", "objective-c",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "jenkins", "gitlab", "github actions", "circleci", "travis",
    "observability", "prometheus", "grafana", "datadog", "splunk",
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _fetch_job_description(url: str) -> Optional[str]:
    """Fetch job description from URL. Returns None if fetch fails."""
    if not url:
        return None
    
    js_sites = ["greenhouse.io", "lever.co", "indeed.com", "linkedin.com", "workday.com"]
    needs_js = any(site in url.lower() for site in js_sites)
    
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            element.decompose()
        
        selectors = [
            "#content", ".content", ".job-description", "#job-description",
            ".description", "#description", ".job-details", "#job-details",
            "#jobDescriptionText", "article", "main", "[role='main']",
        ]
        
        content = None
        for selector in selectors:
            try:
                el = soup.select_one(selector)
                if el:
                    text = el.get_text(separator=" ", strip=True)
                    if len(text) > 200:
                        content = text
                        break
            except:
                continue
        
        if not content:
            body = soup.find("body")
            content = body.get_text(separator=" ", strip=True) if body else ""
        
        content = re.sub(r'\s+', ' ', content)[:10000]
        
        if needs_js and len(content) < 500:
            logger.debug(f"📄 Fetched {len(content)} chars (JS site, may be incomplete)")
        
        return content if len(content) >= 100 else None
        
    except Exception as e:
        logger.debug(f"⚠️ Failed to fetch description: {e}")
        return None


def _get_profile_context() -> Dict[str, Any]:
    """Get profile context for matching."""
    return get_store().get_search_context()


def _get_profile_hash() -> str:
    """Generate hash of current profile for cache invalidation."""
    context = _get_profile_context()
    if not context:
        return ""
    profile_str = str(sorted(context.items()))
    return hashlib.md5(profile_str.encode()).hexdigest()[:8]


def _generate_job_id(job_title: str, company: str, location: str, job_url: str) -> str:
    """Generate consistent job ID (must match job_cache._generate_id)."""
    if job_url:
        return hashlib.md5(job_url.encode()).hexdigest()[:12]
    content = f"{job_title}{company}{location}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def _determine_level(score: int) -> str:
    """Determine match level from score."""
    if score >= 80:
        return "strong"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "partial"
    return "weak"


# =============================================================================
# PASS 1: KEYWORD/REGEX MATCHING (Fast)
# =============================================================================

def keyword_match(
    job_title: str,
    company: str,
    job_description: str,
    location: str,
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Pass 1: Fast keyword-based matching.
    
    Returns:
        Dict with keyword_score, matching_skills, missing_skills, etc.
    """
    user_skills = set(s.lower() for s in profile.get("skills", []))
    target_roles = [r.lower() for r in profile.get("target_roles", [])]
    target_locations = [l.lower() for l in profile.get("target_locations", [])]
    excluded_companies = [c.lower() for c in profile.get("excluded_companies", [])]
    remote_pref = profile.get("remote_preference", "hybrid")
    
    # Check exclusion (substring match for variants like "Amazon.com" matching "amazon")
    company_lower = company.lower()
    for exc in excluded_companies:
        if exc in company_lower:
            return {
                "keyword_score": 0,
                "match_level": "excluded",
                "excluded": True,
                "reason": f"{company} is in exclusion list (matched '{exc}')",
            }
    
    job_desc_lower = job_description.lower() if job_description else ""
    
    # Find skills in job description
    job_skills_found = set()
    for skill in TECH_SKILLS:
        if skill in job_desc_lower:
            job_skills_found.add(skill)
    
    # Skill analysis
    matching_skills = user_skills.intersection(job_skills_found)
    missing_skills = job_skills_found - user_skills
    extra_skills = user_skills - job_skills_found
    
    skill_score = (len(matching_skills) / max(len(job_skills_found), 1)) * 100 if job_skills_found else 50
    
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
    
    if remote_pref == "remote" and not remote_in_job:
        location_score -= 20
    elif remote_pref == "onsite" and remote_in_job:
        location_score -= 10
    
    # Combined score
    keyword_score = int(
        (skill_score * 0.5) +
        (role_score * 0.3) +
        (location_score * 0.2)
    )
    
    # Experience level detection
    exp_patterns = {
        "entry": r"(entry.?level|0-2 years|junior|new grad|associate)",
        "mid": r"(mid.?level|3-5 years|intermediate|2-4 years|3-6 years)",
        "senior": r"(senior|5\+ years|7\+ years|lead|principal|staff|8\+ years|10\+ years)"
    }
    detected_level = "mid"
    for level, pattern in exp_patterns.items():
        if re.search(pattern, job_desc_lower):
            detected_level = level
            break
    
    return {
        "keyword_score": keyword_score,
        "match_level": _determine_level(keyword_score),
        "skill_score": int(skill_score),
        "role_score": role_score,
        "location_score": location_score,
        "matching_skills": list(matching_skills),
        "missing_skills": list(missing_skills),
        "extra_skills": list(extra_skills),
        "role_match": role_match,
        "location_match": location_match,
        "remote_in_job": remote_in_job,
        "detected_level": detected_level,
        "excluded": False,
    }


# =============================================================================
# PASS 2: LLM HOLISTIC ANALYSIS (Slow but thorough)
# =============================================================================

def _get_mlx_model():
    """Lazy-load the MLX model and tokenizer."""
    global _mlx_model, _mlx_tokenizer
    if _mlx_model is None and USE_MLX_MODEL:
        try:
            from mlx_lm import load
            model_path = MLX_MODEL_PATH or "models/job-matcher-lora/fused_model"
            logger.info(f"Loading MLX model from {model_path}")
            _mlx_model, _mlx_tokenizer = load(model_path)
            logger.info("MLX model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load MLX model: {e}")
            raise
    return _mlx_model, _mlx_tokenizer


def _mlx_generate(prompt: str, max_tokens: int = 800, temperature: float = 0.3) -> str:
    """Generate response using MLX model."""
    model, tokenizer = _get_mlx_model()
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler
    
    # Format as chat
    messages = [{"role": "user", "content": prompt}]
    formatted_prompt = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=False
    )
    
    # Create sampler with temperature
    sampler = make_sampler(temp=temperature)
    
    response = generate(
        model, tokenizer,
        prompt=formatted_prompt,
        max_tokens=max_tokens,
        sampler=sampler,
    )
    return response


def llm_match(
    job_title: str,
    company: str,
    job_description: str,
    location: str,
    salary_info: str,
    job_url: str,
    profile: Dict[str, Any],
    keyword_result: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Pass 2: LLM-based holistic analysis.
    
    Args:
        keyword_result: Optional Pass 1 results to include in analysis
    
    Returns:
        Dict with llm_score, toon_report, etc.
    """
    # Build profile summary
    profile_text = f"""CANDIDATE PROFILE:
- Name: {profile.get('name', 'Unknown')}
- Location: {profile.get('location', 'Not specified')}
- Skills: {', '.join(profile.get('skills', [])[:20])}
- Target Roles: {', '.join(profile.get('target_roles', []))}
- Target Locations: {', '.join(profile.get('target_locations', []))}
- Remote Preference: {profile.get('remote_preference', 'hybrid')}
- Salary Range: {profile.get('salary_range', 'Not specified')}
- Summary: {profile.get('resume_summary', 'Not provided')[:400]}"""

    # Include keyword analysis if available
    keyword_context = ""
    if keyword_result:
        keyword_context = f"""
KEYWORD ANALYSIS (Pass 1):
- Keyword Score: {keyword_result.get('keyword_score', 'N/A')}%
- Matching Skills: {', '.join(keyword_result.get('matching_skills', [])[:8])}
- Missing Skills: {', '.join(keyword_result.get('missing_skills', [])[:6])}
- Role Match: {'Yes' if keyword_result.get('role_match') else 'No'}
- Location Match: {'Yes' if keyword_result.get('location_match') else 'No'}
"""

    desc_truncated = job_description[:6000] if job_description else "No description provided"
    
    prompt = f"""Analyze how well this candidate matches the job. Provide a holistic assessment.

{profile_text}
{keyword_context}
JOB POSTING:
- Title: {job_title}
- Company: {company}
- Location: {location}
- Salary: {salary_info if salary_info else 'Not disclosed'}

JOB DESCRIPTION:
{desc_truncated}

SCORING (be thoughtful and realistic):
- 85-100%: Excellent fit - exceeds most requirements
- 70-84%: Good fit - meets core requirements
- 50-69%: Partial fit - some alignment, notable gaps
- 30-49%: Stretch - significant gaps
- 0-29%: Poor fit - major misalignment

OUTPUT EXACTLY IN THIS FORMAT:
[llm_analysis]
score: [NUMBER between 0-100]%
assessment: [2-3 sentence holistic evaluation citing specific job requirements and candidate qualifications]

[key_strengths]
- [strength 1 with evidence]
- [strength 2 with evidence]
- [strength 3 with evidence]

[concerns]
- [concern 1 and how to address]
- [concern 2 and how to address]

[recommendations]
1. [specific application advice]
2. [interview prep suggestion]
3. [skill to emphasize or develop]

Output ONLY the TOON format above, no other text."""

    try:
        # Use MLX model if configured, otherwise use Ollama
        if USE_MLX_MODEL:
            logger.debug("Using MLX model for LLM analysis")
            result = _mlx_generate(prompt, max_tokens=800)
        else:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": FAST_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 800}
                },
                timeout=LLM_TIMEOUT
            )
            response.raise_for_status()
            result = response.json().get("response", "").strip()
        
        # Extract score
        score_match = re.search(r'score:\s*(\d+)%?', result)
        llm_score = int(score_match.group(1)) if score_match else 50
        llm_score = max(0, min(100, llm_score))  # Clamp to 0-100
        
        return {
            "llm_score": llm_score,
            "match_level": _determine_level(llm_score),
            "toon_report": result,
            "llm_success": True,
        }
        
    except requests.exceptions.Timeout:
        logger.warning(f"⚠️ LLM timeout for {job_title[:30]}")
        return {"llm_score": None, "llm_success": False, "error": "timeout"}
    except Exception as e:
        logger.warning(f"⚠️ LLM error: {e}")
        return {"llm_score": None, "llm_success": False, "error": str(e)}


# =============================================================================
# TWO-PASS MATCHING (Combined)
# =============================================================================

def analyze_job_match(
    job_title: str,
    company: str,
    job_description: str,
    location: str = "",
    salary_info: str = "",
    job_url: str = "",
    job_id: str = "",
    use_cache: bool = True,
    fetch_description: bool = True,
    run_llm: bool = False,
) -> Dict[str, Any]:
    """
    Analyze job match using two-pass approach.
    
    Pass 1 (always): Fast keyword/regex matching
    Pass 2 (optional): LLM holistic analysis
    
    Args:
        job_title: Job title
        company: Company name
        job_description: Job description text
        location: Job location
        salary_info: Salary range
        job_url: Job posting URL
        job_id: Optional job ID for cache consistency
        use_cache: Check/use cached results
        fetch_description: Fetch description from URL if missing
        run_llm: Run Pass 2 LLM analysis (slower but more accurate)
    
    Returns:
        Match analysis with keyword_score, llm_score (if run_llm), and combined_score
    """
    # Generate IDs
    if not job_id:
        job_id = _generate_job_id(job_title, company, location, job_url)
    profile_hash = _get_profile_hash()
    
    # Fetch description if needed
    if (not job_description or len(job_description) < 50) and job_url and fetch_description:
        logger.debug(f"📥 Fetching description for: {job_title[:40]}...")
        fetched = _fetch_job_description(job_url)
        if fetched:
            job_description = fetched
    
    # Check cache
    if use_cache:
        cache = get_cache()
        cached = cache.get_match(job_id, profile_hash)
        if cached:
            # Check if we need LLM but don't have it cached
            if run_llm and cached.get("llm_score") is None:
                pass  # Continue to run LLM
            else:
                logger.debug(f"🎯 Cache hit: {job_title[:30]}")
                return {
                    "success": True,
                    "from_cache": True,
                    "job_id": job_id,
                    "keyword_score": cached.get("keyword_score", cached.get("match_score", 0)),
                    "llm_score": cached.get("llm_score"),
                    "combined_score": cached.get("combined_score", cached.get("match_score", 0)),
                    "match_level": cached.get("match_level", "unknown"),
                    "toon_report": cached.get("toon_report", ""),
                }
    
    # Get profile
    profile = _get_profile_context()
    if not profile:
        return {
            "success": False,
            "error": "No profile found. Create one with create_profile.",
            "keyword_score": 0,
        }
    
    # Pass 1: Keyword matching (always runs)
    keyword_result = keyword_match(
        job_title=job_title,
        company=company,
        job_description=job_description,
        location=location,
        profile=profile,
    )
    
    # Check exclusion
    if keyword_result.get("excluded"):
        return {
            "success": True,
            "keyword_score": 0,
            "llm_score": None,
            "combined_score": 0,
            "match_level": "excluded",
            "job_title": job_title,
            "company": company,
            "warning": keyword_result.get("reason"),
        }
    
    # Pass 2: LLM analysis (optional)
    llm_result = None
    if run_llm:
        logger.info(f"🤖 LLM analyzing: {job_title[:40]}...")
        llm_result = llm_match(
            job_title=job_title,
            company=company,
            job_description=job_description,
            location=location,
            salary_info=salary_info,
            job_url=job_url,
            profile=profile,
            keyword_result=keyword_result,
        )
    
    # Calculate combined score
    keyword_score = keyword_result["keyword_score"]
    llm_score = llm_result.get("llm_score") if llm_result else None
    
    if llm_score is not None:
        # Weight: 20% keyword, 80% LLM (LLM provides deeper contextual analysis)
        combined_score = int(keyword_score * 0.2 + llm_score * 0.8)
    else:
        combined_score = keyword_score
    
    # Generate TOON report
    toon_report = _generate_combined_report(
        job_title=job_title,
        company=company,
        location=location,
        salary_info=salary_info,
        job_url=job_url,
        keyword_result=keyword_result,
        llm_result=llm_result,
        combined_score=combined_score,
        profile=profile,
    )
    
    result = {
        "success": True,
        "job_id": job_id,
        "keyword_score": keyword_score,
        "llm_score": llm_score,
        "combined_score": combined_score,
        "match_score": combined_score,  # For backwards compatibility
        "match_level": _determine_level(combined_score),
        "toon_report": toon_report,
        "matching_skills": keyword_result.get("matching_skills", []),
        "missing_skills": keyword_result.get("missing_skills", []),
    }
    
    # Cache result
    if use_cache:
        cache = get_cache()
        cache.add_match(job_id, result, profile_hash)
        logger.info(f"🎯 Cached: {job_title[:30]} kw={keyword_score}% llm={llm_score}% combined={combined_score}%")
    
    return result


def _generate_combined_report(
    job_title: str,
    company: str,
    location: str,
    salary_info: str,
    job_url: str,
    keyword_result: Dict[str, Any],
    llm_result: Optional[Dict[str, Any]],
    combined_score: int,
    profile: Dict[str, Any],
) -> str:
    """Generate combined TOON report from both passes."""
    lines = []
    
    # Header
    lines.append("[job_match_report]")
    lines.append(f"job: {job_title} @ {company}")
    lines.append(f"keyword_score: {keyword_result['keyword_score']}%")
    if llm_result and llm_result.get("llm_score") is not None:
        lines.append(f"llm_score: {llm_result['llm_score']}%")
    lines.append(f"combined_score: {combined_score}%")
    lines.append(f"level: {_determine_level(combined_score)}")
    if job_url:
        lines.append(f"url: {job_url}")
    if location:
        lines.append(f"location: {location}")
    if salary_info:
        lines.append(f"salary: {salary_info}")
    lines.append(f"experience_level: {keyword_result.get('detected_level', 'mid')}")
    lines.append("")
    
    # Keyword Analysis (Pass 1)
    lines.append("[keyword_analysis]")
    lines.append(f"skill_score: {keyword_result.get('skill_score', 0)}%")
    lines.append(f"role_match: {'yes' if keyword_result.get('role_match') else 'no'}")
    lines.append(f"location_match: {'yes' if keyword_result.get('location_match') else 'no'}")
    lines.append(f"remote_option: {'yes' if keyword_result.get('remote_in_job') else 'no'}")
    lines.append("")
    
    # Matching Skills
    lines.append("[matching_skills]")
    matching = keyword_result.get("matching_skills", [])
    if matching:
        for skill in matching[:8]:
            lines.append(f"- {skill}")
    else:
        lines.append("- none identified")
    lines.append("")
    
    # Skill Gaps
    lines.append("[skill_gaps]")
    missing = keyword_result.get("missing_skills", [])
    if missing:
        for skill in missing[:6]:
            lines.append(f"- {skill}")
    else:
        lines.append("- none: profile covers requirements")
    lines.append("")
    
    # LLM Analysis (Pass 2)
    if llm_result and llm_result.get("llm_success"):
        lines.append("[llm_analysis]")
        lines.append(llm_result.get("toon_report", "No detailed analysis available"))
        lines.append("")
    
    # Recommendations
    lines.append("[recommendations]")
    if combined_score >= 80:
        lines.append("1. Strong match - apply with confidence")
        if matching:
            lines.append(f"2. Highlight: {', '.join(matching[:3])}")
    elif combined_score >= 60:
        lines.append("1. Good fit - emphasize your strengths")
        if missing:
            lines.append(f"2. Address gaps: {', '.join(missing[:3])}")
    else:
        lines.append("1. Consider if role aligns with your goals")
        if missing:
            lines.append(f"2. Significant gaps: {', '.join(missing[:4])}")
    
    return "\n".join(lines)


# =============================================================================
# CHECKPOINT/RESUME SUPPORT
# =============================================================================

class MatchingProgress:
    """Manages checkpoint/resume for batch matching jobs."""
    
    def __init__(self, checkpoint_file: Path = None):
        self.checkpoint_file = checkpoint_file or CHECKPOINT_DIR / "matching_progress.json"
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        self._progress = self._load()
    
    def _load(self) -> Dict[str, Any]:
        if self.checkpoint_file.exists():
            try:
                return json.loads(self.checkpoint_file.read_text())
            except:
                pass
        return {"completed": {}, "status": "idle"}
    
    def _save(self):
        self.checkpoint_file.write_text(json.dumps(self._progress, indent=2))
    
    def start(self, total_jobs: int, run_llm: bool = False):
        """Start a new matching session."""
        self._progress = {
            "total_jobs": total_jobs,
            "completed": {},
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "status": "in_progress",
            "run_llm": run_llm,
        }
        self._save()
    
    def mark_complete(self, job_id: str, keyword_score: int, llm_score: Optional[int] = None):
        """Mark a job as completed."""
        self._progress["completed"][job_id] = {
            "keyword_score": keyword_score,
            "llm_score": llm_score,
            "completed_at": datetime.now().isoformat(),
        }
        self._progress["updated_at"] = datetime.now().isoformat()
        self._save()
    
    def is_completed(self, job_id: str) -> bool:
        """Check if job was already processed."""
        return job_id in self._progress.get("completed", {})
    
    def get_completed_count(self) -> int:
        return len(self._progress.get("completed", {}))
    
    def finish(self):
        """Mark session as complete."""
        self._progress["status"] = "complete"
        self._progress["finished_at"] = datetime.now().isoformat()
        self._save()
    
    def clear(self):
        """Clear checkpoint to start fresh."""
        self._progress = {"completed": {}, "status": "idle"}
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get progress summary."""
        completed = self._progress.get("completed", {})
        scores = [v.get("keyword_score", 0) for v in completed.values()]
        return {
            "status": self._progress.get("status", "idle"),
            "total": self._progress.get("total_jobs", 0),
            "completed": len(completed),
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "started_at": self._progress.get("started_at"),
            "updated_at": self._progress.get("updated_at"),
        }


def batch_match(
    jobs: List[Dict[str, Any]],
    run_llm: bool = False,
    resume: bool = True,
    batch_size: int = 10,
    on_progress: callable = None,
) -> Dict[str, Any]:
    """
    Run two-pass matching on a batch of jobs with checkpoint support.
    
    Args:
        jobs: List of job dicts (must have title, company, location, url, description)
        run_llm: Whether to run Pass 2 LLM analysis
        resume: Resume from previous checkpoint if exists
        batch_size: Jobs per checkpoint save
        on_progress: Optional callback(completed, total, job_result)
    
    Returns:
        Summary with results and statistics
    """
    progress = MatchingProgress()
    
    if not resume:
        progress.clear()
    
    if progress._progress.get("status") != "in_progress":
        progress.start(len(jobs), run_llm)
    
    results = {"strong": [], "good": [], "partial": [], "weak": [], "excluded": [], "error": []}
    
    for i, job in enumerate(jobs):
        job_id = job.get("id") or _generate_job_id(
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("url", ""),
        )
        
        # Skip if already completed (resume mode)
        if resume and progress.is_completed(job_id):
            continue
        
        try:
            result = analyze_job_match(
                job_title=job.get("title", "Unknown"),
                company=job.get("company", "Unknown"),
                job_description=job.get("description", ""),
                location=job.get("location", ""),
                salary_info=str(job.get("salary", "")),
                job_url=job.get("url", ""),
                job_id=job_id,
                use_cache=True,
                run_llm=run_llm,
            )
            
            level = result.get("match_level", "error")
            results[level].append({
                "job_id": job_id,
                "title": job.get("title", "")[:50],
                "company": job.get("company", "")[:30],
                "keyword_score": result.get("keyword_score", 0),
                "llm_score": result.get("llm_score"),
                "combined_score": result.get("combined_score", 0),
            })
            
            progress.mark_complete(
                job_id,
                result.get("keyword_score", 0),
                result.get("llm_score"),
            )
            
            if on_progress:
                on_progress(progress.get_completed_count(), len(jobs), result)
            
        except Exception as e:
            logger.error(f"Error matching {job.get('title', 'Unknown')}: {e}")
            results["error"].append({"job_id": job_id, "error": str(e)})
        
        # Checkpoint every batch_size
        if (i + 1) % batch_size == 0:
            logger.info(f"📍 Checkpoint: {progress.get_completed_count()}/{len(jobs)} jobs")
    
    progress.finish()
    
    return {
        "total": len(jobs),
        "processed": progress.get_completed_count(),
        "strong": len(results["strong"]),
        "good": len(results["good"]),
        "partial": len(results["partial"]),
        "weak": len(results["weak"]),
        "excluded": len(results["excluded"]),
        "errors": len(results["error"]),
        "results": results,
        "summary": progress.get_summary(),
    }


# =============================================================================
# FUNCTION TOOLS
# =============================================================================

analyze_job_match_tool = FunctionTool(func=analyze_job_match)

# Legacy agent (kept for backwards compatibility)
job_matcher_agent = LlmAgent(
    name="job_matcher_agent",
    model=LLM_MODEL,
    description="Analyzes job descriptions against user profiles with two-pass matching.",
    instruction=JOB_MATCHER_PROMPT,
    output_key="job_match_report",
    tools=[analyze_job_match_tool],
)

logger.info(f"🎯 Job Matcher initialized (model={LLM_MODEL})")
