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
# Note: Simple section markers like [OPENING], [DATE] are PRESERVED for PDF parsing
TEMPLATE_ARTIFACTS = [
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
    # Instruction markers (parenthetical hints)
    r'\(\d+-\d+ sentences[^)]*\)',
]

# Section markers with instructions - replace with simple markers (for PDF parsing)
SECTION_MARKER_REPLACEMENTS = [
    # [OPENING - 2-3 sentences, ~50 words] -> [OPENING]
    (r'\[OPENING\s*-\s*[^\]]*\]', '[OPENING]'),
    # [BODY PARAGRAPH 1 - 3-4 sentences] -> [BODY PARAGRAPH 1]
    (r'\[BODY PARAGRAPH (\d+)\s*-\s*[^\]]*\]', r'[BODY PARAGRAPH \1]'),
    # [CLOSING - 2-3 sentences] -> [CLOSING]
    (r'\[CLOSING\s*-\s*[^\]]*\]', '[CLOSING]'),
]


def _clean_template_artifacts(content: str) -> str:
    """
    Remove template artifacts and instruction markers from generated content.
    
    Preserves simple section markers like [OPENING], [BODY PARAGRAPH 1], [CLOSING]
    which are needed for PDF parsing. Only removes instructional text within markers.
    
    Args:
        content: Raw LLM-generated content (handles None/empty gracefully)
    
    Returns:
        Cleaned content with artifacts removed but section markers preserved
    """
    if not content:
        return ""
    
    cleaned = content
    
    # First, replace section markers with instructions -> simple markers
    # e.g., [OPENING - 2-3 sentences, ~50 words] -> [OPENING]
    for pattern, replacement in SECTION_MARKER_REPLACEMENTS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    
    # Then remove pure artifacts (placeholders, hints)
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
    Check if content contains template artifacts that indicate incomplete generation.
    
    Checks for:
    - Placeholder patterns like {Current date}, {Company Name}
    - Section markers WITH instructions like [OPENING - 2-3 sentences]
    
    Does NOT flag:
    - Simple section markers like [OPENING], [DATE] which are valid for PDF parsing
    
    Args:
        content: Content to check (handles None/empty gracefully)
    
    Returns:
        Tuple of (has_artifacts: bool, found_artifacts: list)
    """
    if not content:
        return False, []
    
    found = []
    
    # Check for placeholder patterns
    for pattern in TEMPLATE_ARTIFACTS:
        matches = re.findall(pattern, content, flags=re.IGNORECASE)
        found.extend(matches)
    
    # Check for section markers WITH instructions (should have been replaced)
    for pattern, _ in SECTION_MARKER_REPLACEMENTS:
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
6. Resume MUST be 400-600 words to fill exactly 1 page - NOT too short, NOT too long
7. Include 3-4 most relevant roles with achievement bullets
8. Each role needs 3-4 bullet points with specific accomplishments and metrics
9. Skills section: 12-18 relevant skills to demonstrate breadth

STRICT RULES - BULLET POINT FORMAT (CRITICAL):
10. EVERY achievement under each job MUST start with "- " (dash followed by space)
11. Do NOT write experience as plain paragraphs - ALWAYS use bullet points
12. Each bullet point should be on its own line, starting with "- "

STRICT RULES - WRITING STYLE (NO FLUFF):
13. Start EVERY bullet with a strong ACTION VERB (Built, Led, Designed, Implemented, Reduced, etc.)
14. NO fluff words: avoid "responsible for", "helped with", "worked on", "assisted in", "various", "multiple"
15. NO filler phrases: avoid "in order to", "was able to", "successfully", "effectively"
16. Be DIRECT and SPECIFIC - state what you DID and the RESULT
17. Include metrics/numbers when available (%, $, time saved, users impacted)
18. Maximum 12-15 words per bullet - be concise

GOOD BULLET EXAMPLES:
- Built ML pipeline processing 10M daily events, reducing latency 40%
- Led 5-engineer team delivering auth service 2 weeks early
- Designed REST API serving 50K requests/sec with 99.9% uptime

BAD BULLET EXAMPLES (AVOID):
- Was responsible for helping to build various machine learning pipelines
- Worked on multiple projects related to authentication services
- Successfully assisted in the development of API infrastructure

CONTENT DENSITY:
- Summary: 2-3 impactful sentences (40-60 words) - direct, no fluff
- Each bullet: 10-15 words, action verb + accomplishment + metric
- Skills: Technical skills relevant to job, no soft skill padding

OUTPUT FORMAT (follow exactly):
[HEADER]
{name}
{email} | {phone} | {location}

[SUMMARY]
{3-4 sentences tailored to job, 60-80 words}

[SKILLS]
{Comma-separated list of 12-18 relevant skills}

[EXPERIENCE]
{Title} | {Company} | {Start Date} - {End Date}
- {Achievement bullet with action verb and metric, 15-25 words}
- {Achievement bullet with action verb and metric, 15-25 words}
- {Achievement bullet with action verb and metric, 15-25 words}
- {Achievement bullet with action verb and metric, 15-25 words}

{Title} | {Company} | {Start Date} - {End Date}
- {Achievement bullet with action verb and metric, 15-25 words}
- {Achievement bullet with action verb and metric, 15-25 words}
- {Achievement bullet with action verb and metric, 15-25 words}

{Repeat for 1-2 more roles with 3-4 bullets each}

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

STRICT RULES - MOTIVATION:
9. In the OPENING, express genuine motivation for WHY you're interested in THIS COMPANY
10. Connect the company's mission, products, or values to your background/interests
11. Do NOT use generic phrases - be specific about what draws you to the company

STRICT RULES - CONTACT INFO:
12. Do NOT include email, phone, or address in the letter body
13. Contact info will be added as a header separately
14. Do NOT sign off with contact information

OUTPUT FORMAT (follow exactly):
[DATE]
{Current date}

[RECIPIENT]
Hiring Manager
{Company Name}

[OPENING - 2-3 sentences, ~50 words]
{Express genuine motivation for this company + your single strongest qualification}

[BODY PARAGRAPH 1 - 3-4 sentences, ~75 words]
{Your most relevant experience mapped to top job requirement, with specific metric}

[BODY PARAGRAPH 2 - 3-4 sentences, ~75 words]
{Second key strength with specific achievement from profile}

[CLOSING - 2-3 sentences, ~50 words]
{Brief enthusiasm, availability, call to action - NO contact info here}

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
Generate the resume now. Remember: 400-600 words to fill exactly 1 page, only facts from the profile, tailored to the job. Be detailed, not sparse.
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
