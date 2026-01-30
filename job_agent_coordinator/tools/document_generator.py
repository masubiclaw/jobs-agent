"""
Document Generator: LLM-powered resume and cover letter generation.

Generates tailored resumes and cover letters based on user profile and job description.
All facts must be verifiable against the user profile - no hallucination allowed.
"""

import os
import logging
import json
import re
import requests
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

# Template artifact patterns that should be removed from generated content
TEMPLATE_ARTIFACTS = [
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


def _clean_template_artifacts(content: str) -> str:
    """
    Remove template artifacts and instruction markers from generated content.
    
    Args:
        content: Raw LLM-generated content (handles None/empty gracefully)
    
    Returns:
        Cleaned content with artifacts removed
    """
    if not content:
        return ""
    
    cleaned = content
    
    for pattern in TEMPLATE_ARTIFACTS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up excessive whitespace left by removals
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    
    # Remove lines that are just whitespace
    lines = [line for line in cleaned.split('\n') if line.strip()]
    cleaned = '\n'.join(lines)
    
    return cleaned.strip()


def has_template_artifacts(content: str) -> Tuple[bool, List[str]]:
    """
    Check if content contains template artifacts.
    
    Args:
        content: Content to check (handles None/empty gracefully)
    
    Returns:
        Tuple of (has_artifacts: bool, found_artifacts: list)
    """
    if not content:
        return False, []
    
    found = []
    for pattern in TEMPLATE_ARTIFACTS:
        matches = re.findall(pattern, content, flags=re.IGNORECASE)
        found.extend(matches)
    return bool(found), found


# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:12b")
LLM_TIMEOUT = 180  # Longer timeout for document generation


def _call_ollama(prompt: str, temperature: float = 0.3) -> str:
    """Call Ollama API for text generation."""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": 2000}
            },
            timeout=LLM_TIMEOUT
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        raise


def _format_profile_for_prompt(profile: Dict[str, Any]) -> str:
    """Format user profile for inclusion in LLM prompt."""
    # Extract skills as names only
    skills = profile.get("skills", [])
    if skills and isinstance(skills[0], dict):
        skill_names = [s.get("name", "") for s in skills]
    else:
        skill_names = skills
    
    # Format experience
    experience_lines = []
    for exp in profile.get("experience", [])[:6]:  # Include more for selection
        title = exp.get("title", "")
        company = exp.get("company", "")
        start = exp.get("start_date", "")
        end = exp.get("end_date", "")
        desc = exp.get("description", "")
        experience_lines.append(f"""
- Title: {title}
  Company: {company}
  Dates: {start} to {end}
  Description: {desc}""")
    
    # Extract education from notes
    notes = profile.get("notes", "")
    education_section = ""
    if "EDUCATION:" in notes:
        edu_start = notes.find("EDUCATION:")
        edu_end = notes.find("CERTIFICATIONS:", edu_start)
        if edu_end == -1:
            edu_end = len(notes)
        education_section = notes[edu_start:edu_end].strip()
    
    # Extract certifications from notes
    cert_section = ""
    if "CERTIFICATIONS:" in notes:
        cert_start = notes.find("CERTIFICATIONS:")
        cert_section = notes[cert_start:].strip()
    
    return f"""CANDIDATE PROFILE (ONLY use facts from this profile):

Name: {profile.get('name', 'Unknown')}
Email: {profile.get('email', '')}
Phone: {profile.get('phone', '')}
Location: {profile.get('location', '')}

Professional Summary:
{profile.get('resume', {}).get('summary', 'No summary provided')}

Skills (use only these):
{', '.join(skill_names)}

Work Experience (use only these roles):
{''.join(experience_lines)}

{education_section}

{cert_section}
"""


def _format_job_for_prompt(job: Dict[str, Any]) -> str:
    """Format job details for inclusion in LLM prompt."""
    return f"""TARGET JOB:

Title: {job.get('title', 'Unknown')}
Company: {job.get('company', 'Unknown')}
Location: {job.get('location', '')}

Job Description:
{job.get('description', 'No description available')[:3000]}
"""


RESUME_SYSTEM_PROMPT = """You are an expert resume writer. Generate a professional, ATS-optimized resume.

STRICT RULES - FACTS:
1. ONLY use information from the provided profile - NO EXCEPTIONS
2. Do NOT invent skills, experiences, achievements, or metrics
3. Do NOT exaggerate or embellish any information
4. If profile lacks relevant experience, work with what exists
5. Tailor presentation of EXISTING facts to match job requirements

STRICT RULES - LENGTH (CRITICAL):
6. Resume MUST fit on exactly 1 page (~500-600 words max)
7. Include only 3-4 most relevant roles
8. Keep bullet points to 2-3 per role, prioritize impact/metrics
9. Skills section: top 10-15 most relevant skills only
10. No filler words or unnecessary phrases

OUTPUT FORMAT (follow exactly):
[HEADER]
{name}
{email} | {phone} | {location}

[SUMMARY]
{2-3 sentences tailored to job, 50-75 words max}

[SKILLS]
{Comma-separated list of 10-15 relevant skills}

[EXPERIENCE]
{Title} | {Company} | {Start Date} - {End Date}
- {Achievement bullet with metric if available}
- {Achievement bullet with metric if available}
- {Achievement bullet with metric if available}

{Repeat for 2-3 more roles}

[EDUCATION]
{Degree}, {Institution}, {Year}
"""


COVER_LETTER_SYSTEM_PROMPT = """You are an expert cover letter writer. Generate a compelling, concise cover letter.

STRICT RULES - FACTS:
1. ONLY use information from the provided profile - NO EXCEPTIONS
2. Do NOT invent skills, experiences, achievements, or metrics
3. Do NOT exaggerate or embellish any information
4. Reference specific experiences from the profile

STRICT RULES - LENGTH (CRITICAL):
5. Cover letter MUST be 250-350 words maximum (3-4 short paragraphs)
6. NO fluff phrases like "I am writing to express my interest"
7. Every sentence must add value - be direct and specific
8. Focus on 2-3 key qualifications that match the job

OUTPUT FORMAT (follow exactly):
[DATE]
{Current date}

[RECIPIENT]
Hiring Manager
{Company Name}

[OPENING - 2-3 sentences, ~50 words]
{Direct statement about the position and your single strongest qualification}

[BODY PARAGRAPH 1 - 3-4 sentences, ~75 words]
{Your most relevant experience mapped to top job requirement, with specific metric}

[BODY PARAGRAPH 2 - 3-4 sentences, ~75 words]
{Second key strength with specific achievement from profile}

[CLOSING - 2-3 sentences, ~50 words]
{Enthusiasm, availability, call to action}

{Your name}
"""


def generate_resume_content(
    profile: Dict[str, Any],
    job: Dict[str, Any],
    feedback: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate resume content using LLM.
    
    Args:
        profile: User profile dictionary
        job: Job posting dictionary
        feedback: Optional feedback from critic for refinement
    
    Returns:
        Dict with 'content' (resume text) and 'metadata'
    """
    profile_text = _format_profile_for_prompt(profile)
    job_text = _format_job_for_prompt(job)
    
    feedback_section = ""
    if feedback:
        feedback_section = f"""
FEEDBACK FROM PREVIOUS ATTEMPT (address these issues):
{feedback}
"""
    
    prompt = f"""{RESUME_SYSTEM_PROMPT}

{profile_text}

{job_text}
{feedback_section}
Generate the resume now. Remember: 1 page max, only facts from the profile, tailored to the job.
"""
    
    logger.info(f"Generating resume for {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
    
    raw_content = _call_ollama(prompt, temperature=0.3)
    content = _clean_template_artifacts(raw_content)
    
    return {
        "content": content,
        "type": "resume",
        "job_title": job.get("title", ""),
        "company": job.get("company", ""),
        "word_count": len(content.split()),
    }


def generate_cover_letter_content(
    profile: Dict[str, Any],
    job: Dict[str, Any],
    feedback: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate cover letter content using LLM.
    
    Args:
        profile: User profile dictionary
        job: Job posting dictionary
        feedback: Optional feedback from critic for refinement
    
    Returns:
        Dict with 'content' (cover letter text) and 'metadata'
    """
    profile_text = _format_profile_for_prompt(profile)
    job_text = _format_job_for_prompt(job)
    
    feedback_section = ""
    if feedback:
        feedback_section = f"""
FEEDBACK FROM PREVIOUS ATTEMPT (address these issues):
{feedback}
"""
    
    prompt = f"""{COVER_LETTER_SYSTEM_PROMPT}

{profile_text}

{job_text}
{feedback_section}
Generate the cover letter now. Remember: 250-350 words max, only facts from the profile, no fluff.
"""
    
    logger.info(f"Generating cover letter for {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
    
    raw_content = _call_ollama(prompt, temperature=0.4)  # Slightly higher for more natural tone
    content = _clean_template_artifacts(raw_content)
    
    return {
        "content": content,
        "type": "cover_letter",
        "job_title": job.get("title", ""),
        "company": job.get("company", ""),
        "word_count": len(content.split()),
    }
