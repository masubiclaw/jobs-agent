"""
Document Critic: Evaluates resumes and cover letters for quality, ATS compatibility, and fact verification.

Provides scoring and actionable feedback for iterative improvement.
"""

import os
import logging
import json
import re
import requests
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:12b")
LLM_TIMEOUT = 120

# Length constraints
RESUME_MAX_WORDS = 600
COVER_LETTER_MIN_WORDS = 200
COVER_LETTER_MAX_WORDS = 400

# Template artifact patterns that indicate incomplete generation
# Keep in sync with TEMPLATE_ARTIFACTS in document_generator.py
ARTIFACT_PATTERNS = [
    # Section markers with instructions
    r'\[OPENING\s*-\s*[^\]]*\]',
    r'\[BODY PARAGRAPH \d+\s*-\s*[^\]]*\]',
    r'\[CLOSING\s*-\s*[^\]]*\]',
    r'\[DATE\]',
    r'\[RECIPIENT\]',
    # Placeholder patterns
    r'\{Current date\}',
    r'\{Company Name\}',
    r'\{Your name\}',
    r'\{name\}',
    r'\{email\}',
    r'\{phone\}',
    r'\{location\}',
    r'\{[^}]*sentences[^}]*\}',
    r'\{[^}]*words[^}]*\}',
    r'~\d+\s*words?',
    # Instruction markers
    r'\(\d+-\d+ sentences[^)]*\)',
]


def _check_for_artifacts(content: str) -> Tuple[bool, List[str]]:
    """
    Check if content contains template artifacts that indicate incomplete generation.
    
    Args:
        content: Content to check (handles None/empty gracefully)
    
    Returns:
        Tuple of (has_artifacts, list of found artifacts)
    """
    if not content:
        return False, []
    
    found = []
    for pattern in ARTIFACT_PATTERNS:
        matches = re.findall(pattern, content, flags=re.IGNORECASE)
        found.extend(matches)
    return bool(found), found


@dataclass
class CritiqueResult:
    """Result of document critique."""
    fact_score: int  # 0-100, must be 100 to pass
    keyword_score: int  # 0-100
    ats_score: int  # 0-100
    overall_score: int  # 0-100 weighted average
    length_compliant: bool
    length_feedback: str
    verified_facts: List[str]
    unverified_facts: List[str]
    fabricated_facts: List[str]
    suggestions: List[str]
    passed: bool
    has_artifacts: bool = False
    found_artifacts: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.found_artifacts is None:
            self.found_artifacts = []


def _call_ollama(prompt: str, temperature: float = 0.1) -> str:
    """Call Ollama API for analysis."""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": 1500}
            },
            timeout=LLM_TIMEOUT
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        raise


def _extract_profile_facts(profile: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract all verifiable facts from profile."""
    facts = {
        "skills": [],
        "companies": [],
        "titles": [],
        "dates": [],
        "metrics": [],
        "education": [],
        "certifications": [],
        "locations": [],
    }
    
    # Extract skills
    skills = profile.get("skills", [])
    for skill in skills:
        if isinstance(skill, dict):
            facts["skills"].append(skill.get("name", "").lower())
        else:
            facts["skills"].append(str(skill).lower())
    
    # Extract experience facts
    for exp in profile.get("experience", []):
        facts["companies"].append(exp.get("company", "").lower())
        facts["titles"].append(exp.get("title", "").lower())
        facts["dates"].append(exp.get("start_date", ""))
        facts["dates"].append(exp.get("end_date", ""))
        
        # Extract metrics from description (numbers with context)
        desc = exp.get("description", "")
        metrics = re.findall(r'\$?[\d,]+\.?\d*[%KMB]?(?:\+|\s|/|-|to)', desc)
        facts["metrics"].extend(metrics)
    
    # Extract from notes (education, certifications)
    notes = profile.get("notes", "")
    if "Master" in notes:
        facts["education"].append("master")
    if "Bachelor" in notes:
        facts["education"].append("bachelor")
    if "PhD" in notes or "Doctorate" in notes:
        facts["education"].append("phd")
    
    # Location
    facts["locations"].append(profile.get("location", "").lower())
    
    return facts


def _check_length_compliance(content: str, doc_type: str) -> Tuple[bool, str]:
    """Check if document meets length requirements."""
    word_count = len(content.split())
    
    if doc_type == "resume":
        if word_count > RESUME_MAX_WORDS:
            return False, f"Resume too long: {word_count} words (max {RESUME_MAX_WORDS}). Remove less relevant content."
        return True, f"Resume length OK: {word_count} words"
    
    elif doc_type == "cover_letter":
        if word_count < COVER_LETTER_MIN_WORDS:
            return False, f"Cover letter too short: {word_count} words (min {COVER_LETTER_MIN_WORDS}). Add more substance."
        if word_count > COVER_LETTER_MAX_WORDS:
            return False, f"Cover letter too long: {word_count} words (max {COVER_LETTER_MAX_WORDS}). Be more concise."
        return True, f"Cover letter length OK: {word_count} words"
    
    return True, "Unknown document type"


def _extract_keywords_from_job(job: Dict[str, Any]) -> List[str]:
    """Extract important keywords from job description."""
    description = job.get("description", "").lower()
    title = job.get("title", "").lower()
    
    # Common tech keywords to look for
    tech_keywords = [
        "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
        "react", "angular", "vue", "node", "django", "flask", "spring",
        "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
        "sql", "postgresql", "mysql", "mongodb", "redis",
        "machine learning", "ml", "ai", "deep learning", "nlp",
        "agile", "scrum", "devops", "ci/cd", "git",
        "api", "rest", "graphql", "microservices",
        "leadership", "management", "team lead", "architect",
    ]
    
    found_keywords = []
    for kw in tech_keywords:
        if kw in description or kw in title:
            found_keywords.append(kw)
    
    return found_keywords


def _calculate_keyword_match(content: str, job_keywords: List[str]) -> Tuple[int, List[str], List[str]]:
    """Calculate keyword match score."""
    content_lower = content.lower()
    matched = []
    missing = []
    
    for kw in job_keywords:
        if kw in content_lower:
            matched.append(kw)
        else:
            missing.append(kw)
    
    if not job_keywords:
        return 100, [], []
    
    score = int((len(matched) / len(job_keywords)) * 100)
    return score, matched, missing


FACT_CHECK_PROMPT = """You are a fact-checker for resumes and cover letters. Your job is to verify that ALL claims in the document can be traced back to the provided profile.

PROFILE DATA (source of truth):
{profile_data}

DOCUMENT TO CHECK:
{document}

TASK: Identify every factual claim in the document and categorize it:

1. VERIFIED - The claim directly matches information in the profile
2. UNVERIFIED - The claim could be true but isn't explicitly in the profile
3. FABRICATED - The claim is clearly NOT in the profile (invented)

Focus on:
- Job titles (must match profile exactly)
- Company names (must match profile exactly)
- Skills/technologies (must be in profile skills list)
- Metrics/numbers (must appear in profile descriptions)
- Dates/timeframes (must match profile dates)
- Education/certifications (must be in profile)

OUTPUT FORMAT (JSON):
{{
    "verified_facts": ["fact1", "fact2"],
    "unverified_facts": ["fact3"],
    "fabricated_facts": ["fact4"],
    "fact_score": 0-100
}}

If ANY fabricated facts are found, fact_score MUST be 0.
"""


ATS_CHECK_PROMPT = """You are an ATS (Applicant Tracking System) analyzer. Evaluate this document for ATS compatibility.

DOCUMENT:
{document}

DOCUMENT TYPE: {doc_type}

Check for:
1. Clear section headers (EXPERIENCE, SKILLS, EDUCATION, etc.)
2. Standard date formats (Month YYYY or YYYY)
3. No tables, graphics, or complex formatting
4. Contact information present
5. Relevant keywords for the job
6. Professional language
7. Proper grammar and spelling
8. Achievement-focused bullet points (for resumes)

OUTPUT FORMAT (JSON):
{{
    "ats_score": 0-100,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}
"""


def critique_document(
    content: str,
    doc_type: str,
    profile: Dict[str, Any],
    job: Dict[str, Any]
) -> CritiqueResult:
    """
    Critique a resume or cover letter.
    
    Args:
        content: The document content to critique
        doc_type: "resume" or "cover_letter"
        profile: User profile for fact verification
        job: Job posting for keyword matching
    
    Returns:
        CritiqueResult with scores and feedback
    """
    logger.info(f"Critiquing {doc_type}...")
    
    # 0. Check for template artifacts (should be cleaned but verify)
    has_artifacts, found_artifacts = _check_for_artifacts(content)
    if has_artifacts:
        logger.warning(f"Template artifacts found in {doc_type}: {found_artifacts[:3]}")
    
    # 1. Check length compliance
    length_ok, length_feedback = _check_length_compliance(content, doc_type)
    
    # 2. Extract job keywords and check match
    job_keywords = _extract_keywords_from_job(job)
    keyword_score, matched_kw, missing_kw = _calculate_keyword_match(content, job_keywords)
    
    # 3. Fact verification via LLM
    profile_facts = _extract_profile_facts(profile)
    profile_summary = f"""
Name: {profile.get('name')}
Location: {profile.get('location')}
Skills: {', '.join(profile_facts['skills'][:30])}
Companies worked at: {', '.join(set(profile_facts['companies']))}
Job titles held: {', '.join(set(profile_facts['titles']))}
"""
    
    for exp in profile.get('experience', [])[:4]:
        profile_summary += f"\nRole: {exp.get('title')} at {exp.get('company')} ({exp.get('start_date')} - {exp.get('end_date')})"
        profile_summary += f"\nDescription: {exp.get('description', '')[:500]}"
    
    profile_summary += f"\n\nNotes: {profile.get('notes', '')[:500]}"
    
    fact_prompt = FACT_CHECK_PROMPT.format(
        profile_data=profile_summary,
        document=content
    )
    
    try:
        fact_response = _call_ollama(fact_prompt)
        # Extract JSON from response
        json_match = re.search(r'\{[^}]+\}', fact_response, re.DOTALL)
        if json_match:
            fact_data = json.loads(json_match.group())
        else:
            fact_data = {"verified_facts": [], "unverified_facts": [], "fabricated_facts": [], "fact_score": 50}
    except Exception as e:
        logger.warning(f"Fact check parsing failed: {e}")
        fact_data = {"verified_facts": [], "unverified_facts": [], "fabricated_facts": [], "fact_score": 50}
    
    # 4. ATS compatibility check via LLM
    ats_prompt = ATS_CHECK_PROMPT.format(document=content, doc_type=doc_type)
    
    try:
        ats_response = _call_ollama(ats_prompt)
        json_match = re.search(r'\{[^}]+\}', ats_response, re.DOTALL)
        if json_match:
            ats_data = json.loads(json_match.group())
        else:
            ats_data = {"ats_score": 70, "issues": [], "suggestions": []}
    except Exception as e:
        logger.warning(f"ATS check parsing failed: {e}")
        ats_data = {"ats_score": 70, "issues": [], "suggestions": []}
    
    # 5. Calculate overall score
    fact_score = fact_data.get("fact_score", 50)
    ats_score = ats_data.get("ats_score", 70)
    
    # If fabricated facts found, set fact_score to 0
    if fact_data.get("fabricated_facts"):
        fact_score = 0
    
    # Weighted average (facts are critical)
    overall_score = int(fact_score * 0.4 + keyword_score * 0.3 + ats_score * 0.3)
    
    # 6. Compile suggestions
    suggestions = ats_data.get("suggestions", [])
    if has_artifacts:
        suggestions.insert(0, f"CRITICAL: Remove template artifacts: {', '.join(found_artifacts[:3])}")
    if missing_kw:
        suggestions.append(f"Add missing keywords: {', '.join(missing_kw[:5])}")
    if not length_ok:
        suggestions.insert(0, length_feedback)
    
    # 7. Determine pass/fail (artifacts cause automatic failure)
    passed = (
        fact_score >= 100 and
        overall_score >= 75 and
        length_ok and
        not fact_data.get("fabricated_facts") and
        not has_artifacts
    )
    
    return CritiqueResult(
        fact_score=fact_score,
        keyword_score=keyword_score,
        ats_score=ats_score,
        overall_score=overall_score,
        length_compliant=length_ok,
        length_feedback=length_feedback,
        verified_facts=fact_data.get("verified_facts", []),
        unverified_facts=fact_data.get("unverified_facts", []),
        fabricated_facts=fact_data.get("fabricated_facts", []),
        suggestions=suggestions,
        passed=passed,
        has_artifacts=has_artifacts,
        found_artifacts=found_artifacts,
    )


def format_critique_feedback(critique: CritiqueResult) -> str:
    """Format critique result as feedback string for regeneration."""
    feedback_parts = []
    
    if critique.has_artifacts:
        feedback_parts.append(f"CRITICAL: Remove template artifacts like {', '.join(critique.found_artifacts[:3])}. Generate actual content, not placeholders.")
    
    if critique.fabricated_facts:
        feedback_parts.append(f"CRITICAL: Remove fabricated facts: {', '.join(critique.fabricated_facts)}")
    
    if not critique.length_compliant:
        feedback_parts.append(f"LENGTH: {critique.length_feedback}")
    
    if critique.keyword_score < 70:
        feedback_parts.append(f"KEYWORDS: Low keyword match ({critique.keyword_score}%). Add more job-relevant keywords.")
    
    if critique.suggestions:
        feedback_parts.append(f"SUGGESTIONS: {'; '.join(critique.suggestions[:3])}")
    
    return "\n".join(feedback_parts)
