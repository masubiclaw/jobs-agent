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
    # Word count lines that LLM sometimes adds
    r'^Word Count:?\s*\d+\s*$',
    r'^\*?Word Count:?\s*\d+\*?\s*$',
    r'^Total Words?:?\s*\d+\s*$',
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

# Character replacements for sanitizing LLM output
# Maps problematic Unicode characters to their ASCII equivalents
CHARACTER_REPLACEMENTS = {
    # Smart/curly quotes to straight quotes
    '\u2018': "'",   # Left single quote '
    '\u2019': "'",   # Right single quote '
    '\u201A': "'",   # Single low-9 quote ‚
    '\u201B': "'",   # Single high-reversed-9 quote ‛
    '\u2032': "'",   # Prime ′
    '\u2035': "'",   # Reversed prime ‵
    '\u201C': '"',   # Left double quote "
    '\u201D': '"',   # Right double quote "
    '\u201E': '"',   # Double low-9 quote „
    '\u201F': '"',   # Double high-reversed-9 quote ‟
    '\u2033': '"',   # Double prime ″
    '\u2036': '"',   # Reversed double prime ‶
    '\u00AB': '"',   # Left-pointing double angle «
    '\u00BB': '"',   # Right-pointing double angle »
    
    # Dashes
    '\u2013': '-',   # En-dash –
    '\u2014': '--',  # Em-dash —
    '\u2015': '--',  # Horizontal bar ―
    '\u2012': '-',   # Figure dash ‒
    '\u2010': '-',   # Hyphen ‐
    '\u2011': '-',   # Non-breaking hyphen ‑
    
    # Ellipsis
    '\u2026': '...',  # Horizontal ellipsis …
    
    # Spaces
    '\u00A0': ' ',   # Non-breaking space
    '\u2002': ' ',   # En space
    '\u2003': ' ',   # Em space
    '\u2004': ' ',   # Three-per-em space
    '\u2005': ' ',   # Four-per-em space
    '\u2006': ' ',   # Six-per-em space
    '\u2007': ' ',   # Figure space
    '\u2008': ' ',   # Punctuation space
    '\u2009': ' ',   # Thin space
    '\u200A': ' ',   # Hair space
    '\u200B': '',    # Zero-width space (remove)
    '\u202F': ' ',   # Narrow no-break space
    '\u205F': ' ',   # Medium mathematical space
    '\u3000': ' ',   # Ideographic space
    '\uFEFF': '',    # BOM / Zero-width no-break space (remove)
    
    # Bullets and symbols
    '\u2022': '-',   # Bullet •
    '\u2023': '-',   # Triangular bullet ‣
    '\u2043': '-',   # Hyphen bullet ⁃
    '\u25AA': '-',   # Black small square ▪
    '\u25CF': '-',   # Black circle ●
    '\u25E6': '-',   # White bullet ◦
    
    # Other common substitutions
    '\u00B7': '-',   # Middle dot ·
    '\u2027': '-',   # Hyphenation point ‧
    '\u00D7': 'x',   # Multiplication sign ×
    '\u00F7': '/',   # Division sign ÷
    '\u2212': '-',   # Minus sign −
    '\u00B1': '+/-', # Plus-minus sign ±
    '\u00AE': '(R)', # Registered trademark ®
    '\u2122': '(TM)', # Trademark ™
    '\u00A9': '(C)', # Copyright ©
}


def _sanitize_characters(content: str) -> str:
    """
    Replace problematic Unicode characters with ASCII equivalents.
    
    LLMs often generate smart quotes, em-dashes, and other Unicode characters
    that can cause display issues or look inconsistent in PDFs.
    
    Args:
        content: Raw text content
    
    Returns:
        Sanitized content with ASCII-safe characters
    """
    if not content:
        return ""
    
    result = content
    for unicode_char, replacement in CHARACTER_REPLACEMENTS.items():
        result = result.replace(unicode_char, replacement)
    
    return result


def _clean_markdown(content: str) -> str:
    """
    Remove markdown formatting from LLM-generated content.
    
    LLMs often add markdown despite being told not to. This removes:
    - **bold** and __bold__
    - *italic* and _italic_
    - # headers
    - ``` code blocks
    
    Args:
        content: Raw text content
    
    Returns:
        Content with markdown formatting removed
    """
    if not content:
        return ""
    
    result = content
    
    # Remove bold markers
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)  # **bold**
    result = re.sub(r'__([^_]+)__', r'\1', result)      # __bold__
    
    # Remove italic markers (but preserve underscores in words like snake_case)
    result = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', result)  # *italic*
    result = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', result)    # _italic_
    
    # Remove header markers at start of lines
    result = re.sub(r'^#{1,6}\s+', '', result, flags=re.MULTILINE)
    
    # Remove code block markers
    result = re.sub(r'```[^\n]*\n?', '', result)
    
    return result


def _clean_template_artifacts(content: str) -> str:
    """
    Remove template artifacts, sanitize characters, and clean generated content.
    
    Preserves simple section markers like [OPENING], [BODY PARAGRAPH 1], [CLOSING]
    which are needed for PDF parsing. Only removes instructional text within markers.
    
    Args:
        content: Raw LLM-generated content (handles None/empty gracefully)
    
    Returns:
        Cleaned content with artifacts removed, characters sanitized, section markers preserved
    """
    if not content:
        return ""
    
    # First, sanitize problematic Unicode characters (smart quotes, em-dashes, etc.)
    cleaned = _sanitize_characters(content)
    
    # Remove markdown formatting (LLMs often add it despite instructions)
    cleaned = _clean_markdown(cleaned)
    
    # Replace section markers with instructions -> simple markers
    # e.g., [OPENING - 2-3 sentences, ~50 words] -> [OPENING]
    for pattern, replacement in SECTION_MARKER_REPLACEMENTS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    
    # Then remove pure artifacts (placeholders, hints)
    for pattern in TEMPLATE_ARTIFACTS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    
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
        cert_end = notes.find("PUBLICATIONS:", cert_start)
        if cert_end == -1:
            cert_end = len(notes)
        cert_section = notes[cert_start:cert_end].strip()
    
    # Extract publications from notes
    pub_section = ""
    if "PUBLICATIONS:" in notes:
        pub_start = notes.find("PUBLICATIONS:")
        pub_section = notes[pub_start:].strip()
    
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

{pub_section}
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


# Resume sections in order
RESUME_SECTIONS = ["header", "summary", "skills", "experience", "education", "publications"]

# Section-specific prompts for targeted generation
SECTION_PROMPTS = {
    "header": """Generate ONLY the header section for a resume.

PROFILE:
Name: {name}
Email: {email}
Phone: {phone}
Location: {location}

OUTPUT FORMAT (follow exactly):
[HEADER]
{name}
{email} | {phone} | {location}

FACTUAL ACCURACY RULES (CRITICAL):
1. Use EXACTLY the name, email, phone, and location provided above
2. Do NOT add titles, credentials, or suffixes not in profile
3. Do NOT add LinkedIn, GitHub, or portfolio links unless provided

FABRICATION EXAMPLES (these cause failure):
- Profile: "John Smith" -> Resume: "John Smith, PhD" (WRONG - credential added)
- Profile has no LinkedIn -> Resume adds LinkedIn URL (WRONG - invented)
""",

    "summary": """Generate ONLY the professional summary section for a resume.

PROFILE SUMMARY:
{profile_summary}

EXPERIENCE HISTORY (for calculating years):
{experience}

TARGET JOB:
Title: {job_title}
Company: {job_company}
Description: {job_description}

{feedback_section}

OUTPUT FORMAT (follow exactly):
[SUMMARY]
{{2-3 sentences tailored to the job, 40-60 words}}

FACTUAL ACCURACY RULES (CRITICAL - violations cause failure):
1. Reference ONLY companies that appear in the experience list above
2. Reference ONLY job titles that appear in the experience list above
3. Do NOT invent years of experience - calculate from the earliest start date to present
4. Do NOT claim expertise in technologies not mentioned in profile
5. Do NOT add certifications, degrees, or achievements not in profile

CALCULATING YEARS OF EXPERIENCE:
- Look at the earliest start date in experience history
- Calculate years from that date to present (2026)
- Round to nearest whole number
- Example: If earliest job started 2018, say "8 years of experience"

RULES:
- Write 2-3 impactful sentences (40-60 words total)
- Highlight experience relevant to the target job
- Use ONLY facts from the profile summary and experience
- No fluff phrases like "results-driven professional", "passionate about"
- NO markdown formatting (no **bold**, no *italic*)

FABRICATION EXAMPLES (these cause failure):
- Profile shows jobs from 2020-2026 -> "10+ years of experience" (WRONG - only 6 years)
- Profile has no AWS experience -> "cloud infrastructure expert" (WRONG - not in profile)
- Profile shows "Engineer" title -> "Senior Engineer with..." (WRONG - title upgraded)
""",

    "skills": """Generate ONLY the skills section for a resume.

AVAILABLE SKILLS FROM PROFILE (ONLY use these):
{skills}

TARGET JOB:
Title: {job_title}
Company: {job_company}
Key Requirements: {job_keywords}

{feedback_section}

OUTPUT FORMAT (follow exactly):
[SKILLS]
{{Comma-separated list of 12-18 relevant skills}}

FACTUAL ACCURACY RULES (CRITICAL):
1. ONLY include skills that appear in the AVAILABLE SKILLS list above
2. Use EXACT skill names as written - do NOT paraphrase or substitute
3. Do NOT add skills the job requires if they are NOT in the profile
4. Better to have fewer accurate skills than more fabricated ones

RULES:
- Select 12-18 skills MOST relevant to the target job
- Put most relevant skills first (those matching job requirements)
- NO markdown formatting

FABRICATION EXAMPLES (these cause failure):
- Profile has "Python" -> Resume adds "Python 3.11" (WRONG - version invented)
- Profile has "AWS" -> Resume adds "AWS, Azure, GCP" (WRONG - Azure/GCP not in profile)
- Job requires "Kubernetes" but profile doesn't have it -> Adding "Kubernetes" (WRONG)
- Profile has "React" -> Resume says "React.js, React Native" (WRONG - only "React" is in profile)
""",

    "experience": """Generate ONLY the experience section for a resume.

WORK EXPERIENCE FROM PROFILE:
{experience}

TARGET JOB:
Title: {job_title}
Company: {job_company}
Description: {job_description}

{feedback_section}

OUTPUT FORMAT (follow exactly):
[EXPERIENCE]
{{Title}} | {{Company}} | {{Start Date}} - {{End Date}}
- {{Achievement bullet with action verb, 15-25 words}}
- {{Achievement bullet with action verb, 15-25 words}}
- {{Achievement bullet with action verb, 15-25 words}}

{{Repeat for 2-3 more relevant roles}}

FACTUAL ACCURACY RULES (CRITICAL - violations cause failure):
1. COPY job title EXACTLY as written in profile - do NOT paraphrase or upgrade
2. COPY company name EXACTLY as written in profile - do NOT abbreviate or change
3. ONLY include metrics/numbers that appear VERBATIM in profile description
4. If NO metric exists in profile, describe the work WITHOUT inventing numbers
5. Achievements MUST be derived from profile description text, not invented
6. Do NOT add percentages, dollar amounts, or team sizes unless explicitly stated

STRICT RULES:
1. Include 3-4 most relevant roles with 3-4 bullets each
2. Use EXACT dates from profile - format as "Mon YYYY" (e.g., "Aug 2025")
3. Convert: "2025-08" → "Aug 2025", "present" → "Present"
4. Do NOT change, estimate, or round any dates
5. Start EVERY bullet with a strong ACTION VERB (Built, Led, Designed, Implemented, etc.)
6. Each bullet: 15-25 words - be specific but do NOT invent details
7. NO fluff words: avoid "responsible for", "helped with", "worked on"
8. NO markdown formatting (no **bold**, no *italic*)

WHAT IS ALLOWED vs FABRICATED:
- ALLOWED: Reordering words - "Led team of 5" -> "Led 5-person team"
- ALLOWED: Condensing - "responsible for building" -> "Built"
- FABRICATED: Inventing metrics - Profile has no % -> Resume says "reduced latency 40%"
- FABRICATED: Upgrading titles - "Engineer" -> "Senior Engineer"
- FABRICATED: Adding specifics - Profile says "improved performance" -> Resume says "improved by 50%"

If profile description lacks metrics, write achievement WITHOUT numbers:
- Profile: "Improved system performance"
- GOOD: "Optimized system performance through caching and query improvements"
- BAD: "Improved system performance by 40%" (metric invented)
""",

    "education": """Generate ONLY the education section for a resume.

EDUCATION FROM PROFILE:
{education}

{feedback_section}

OUTPUT FORMAT (follow exactly):
[EDUCATION]
{{Degree}}, {{Institution}}, {{Year}}

FACTUAL ACCURACY RULES (CRITICAL):
1. COPY degree names EXACTLY as written in profile
2. COPY institution names EXACTLY as written in profile
3. COPY years EXACTLY as written in profile
4. Do NOT upgrade degrees (e.g., "BS" to "MS")
5. Do NOT add certifications or courses not in profile

RULES:
- Use ONLY education information from the profile
- Keep it concise - one line per degree
- NO markdown formatting

FABRICATION EXAMPLES (these cause failure):
- Profile: "BS Computer Science" -> Resume: "MS Computer Science" (WRONG - upgraded)
- Profile: "Stanford University" -> Resume: "Stanford University, summa cum laude" (WRONG - honors invented)
- Profile has no MBA -> Resume: "MBA, Business Administration" (WRONG - degree invented)
""",

    "publications": """Generate ONLY the publications section for a resume (if applicable).

PUBLICATIONS FROM PROFILE:
{publications}

TARGET JOB:
Title: {job_title}
Company: {job_company}

{feedback_section}

OUTPUT FORMAT (follow exactly, or empty if no publications):
[PUBLICATIONS]
{{Title}} - {{Venue/Publisher}}, {{Year}}

FACTUAL ACCURACY RULES (CRITICAL):
1. COPY publication titles EXACTLY as written in profile
2. COPY venue/publisher names EXACTLY as written in profile
3. COPY years EXACTLY as written in profile
4. Do NOT invent any publications
5. If profile has no publications, output ONLY: [PUBLICATIONS]

RULES:
- Include ONLY if publications exist in profile AND are relevant to the job
- NO markdown formatting

FABRICATION EXAMPLES (these cause failure):
- Profile has no publications -> Resume lists any publication (WRONG - invented)
- Profile: "Conference Paper at ICML" -> Resume: "Best Paper at ICML" (WRONG - award invented)
- Profile: "2020" -> Resume: "2021" (WRONG - year changed)
""",
}


RESUME_SYSTEM_PROMPT = """You are an expert resume writer. Generate a professional, ATS-optimized resume.

STRICT RULES - FACTS:
1. ONLY use information from the provided profile - NO EXCEPTIONS
2. Do NOT invent skills, experiences, achievements, or metrics
3. Do NOT exaggerate or embellish any information
4. If profile lacks relevant experience, work with what exists
5. Tailor presentation of EXISTING facts to match job requirements

STRICT RULES - DATES (CRITICAL):
6. Use EXACT dates from the profile - do NOT change, estimate, or round them
7. Format: "Mon YYYY" (e.g., "Aug 2025", "Oct 2023", "Present")
8. Convert profile dates: "2025-08" → "Aug 2025", "present" → "Present"
9. Do NOT invent, guess, or approximate any dates
10. If a date is missing, omit that role entirely rather than guess

STRICT RULES - LENGTH (CRITICAL):
11. Resume MUST be 400-600 words to fill exactly 1 page - NOT too short, NOT too long
12. Include 3-4 most relevant roles with achievement bullets
13. Each role needs 3-4 bullet points with specific accomplishments and metrics
14. Skills section: 12-18 relevant skills to demonstrate breadth

STRICT RULES - BULLET POINT FORMAT (CRITICAL):
15. EVERY achievement under each job MUST start with "- " (dash followed by space)
16. Do NOT write experience as plain paragraphs - ALWAYS use bullet points
17. Each bullet point should be on its own line, starting with "- "

STRICT RULES - WRITING STYLE (NO FLUFF):
18. Start EVERY bullet with a strong ACTION VERB (Built, Led, Designed, Implemented, Reduced, etc.)
19. NO fluff words: avoid "responsible for", "helped with", "worked on", "assisted in", "various", "multiple"
20. NO filler phrases: avoid "in order to", "was able to", "successfully", "effectively"
21. Be DIRECT and SPECIFIC - state what you DID and the RESULT
22. Include metrics/numbers when available (%, $, time saved, users impacted)
23. Maximum 12-15 words per bullet - be concise

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

[PUBLICATIONS] (include if candidate has publications and relevant to job)
{Title} - {Venue/Publisher}, {Year}
"""


COVER_LETTER_SYSTEM_PROMPT = """You are an expert cover letter writer. Generate a compelling, concise, grammatically perfect cover letter.

STRICT RULES - GRAMMAR & STYLE (CRITICAL):
1. Use PERFECT grammar - no errors in subject-verb agreement, tense, or punctuation
2. Write in FIRST PERSON consistently ("I led", "I developed", not mixing perspectives)
3. Use ACTIVE VOICE - "I led the team" not "the team was led by me"
4. Each sentence must be COMPLETE with subject and verb
5. Use professional, formal tone throughout
6. PROOFREAD for: run-on sentences, comma splices, sentence fragments
7. Vary sentence structure - avoid starting every sentence with "I"

STRICT RULES - FACTS:
8. ONLY use information from the provided profile - NO EXCEPTIONS
9. Do NOT invent skills, experiences, achievements, or metrics
10. Do NOT exaggerate or embellish any information
11. Reference specific experiences from the profile

STRICT RULES - LENGTH (CRITICAL):
12. Cover letter MUST be 250-350 words maximum (3-4 short paragraphs)
13. NO fluff phrases like "I am writing to express my interest"
14. Every sentence must add value - be direct and specific
15. Focus on 2-3 key qualifications that match the job

STRICT RULES - MOTIVATION:
16. In the OPENING, express genuine motivation for WHY you're interested in THIS COMPANY
17. Connect the company's mission, products, or values to your background/interests
18. Do NOT use generic phrases - be specific about what draws you to the company

STRICT RULES - CONTACT INFO & SIGNATURE:
19. Do NOT include email, phone, or address in the letter body
20. Contact info will be added as a header separately
21. Do NOT sign off with contact information
22. Do NOT put your name at the end - it will be added automatically

OUTPUT FORMAT (follow exactly):
[DATE]
{Current date}

[RECIPIENT]
Hiring Manager
{Company Name}

[OPENING]
{2-3 sentences, ~50 words: Express genuine motivation for this company + your single strongest qualification}

[BODY PARAGRAPH 1]
{3-4 sentences, ~75 words: Your most relevant experience mapped to top job requirement, with specific metric}

[BODY PARAGRAPH 2]
{3-4 sentences, ~75 words: Second key strength with specific achievement from profile}

[CLOSING]
{2-3 sentences, ~50 words: Brief enthusiasm, availability, call to action - NO name here}
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


def _extract_section_data(profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract and format data needed for section-specific prompts.
    
    Returns dict with formatted strings for each section prompt template.
    """
    # Extract skills
    skills = profile.get("skills", [])
    if skills and isinstance(skills[0], dict):
        skill_names = [s.get("name", "") for s in skills]
    else:
        skill_names = skills
    
    # Format experience
    experience_lines = []
    for exp in profile.get("experience", [])[:6]:
        title = exp.get("title", "")
        company = exp.get("company", "")
        start = exp.get("start_date", "")
        end = exp.get("end_date", "")
        desc = exp.get("description", "")
        experience_lines.append(f"""
Title: {title}
Company: {company}
Dates: {start} to {end}
Description: {desc}
""")
    
    # Extract education from notes
    notes = profile.get("notes", "")
    education_section = ""
    if "EDUCATION:" in notes:
        edu_start = notes.find("EDUCATION:")
        edu_end = notes.find("CERTIFICATIONS:", edu_start)
        if edu_end == -1:
            edu_end = notes.find("PUBLICATIONS:", edu_start)
        if edu_end == -1:
            edu_end = len(notes)
        education_section = notes[edu_start:edu_end].strip()
    
    # Extract publications from notes
    pub_section = ""
    if "PUBLICATIONS:" in notes:
        pub_start = notes.find("PUBLICATIONS:")
        pub_section = notes[pub_start:].strip()
    
    # Extract job keywords
    job_desc = job.get("description", "").lower()
    job_keywords = []
    tech_keywords = [
        "python", "java", "javascript", "typescript", "go", "rust", "c++",
        "react", "angular", "vue", "node", "django", "flask",
        "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
        "sql", "postgresql", "mongodb", "redis",
        "machine learning", "ml", "ai", "deep learning",
        "agile", "scrum", "devops", "ci/cd",
    ]
    for kw in tech_keywords:
        if kw in job_desc:
            job_keywords.append(kw)
    
    return {
        "name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "location": profile.get("location", ""),
        "profile_summary": profile.get("resume", {}).get("summary", ""),
        "skills": ", ".join(skill_names),
        "experience": "\n".join(experience_lines),
        "education": education_section,
        "publications": pub_section,
        "job_title": job.get("title", ""),
        "job_company": job.get("company", ""),
        "job_description": job.get("description", "")[:2000],
        "job_keywords": ", ".join(job_keywords[:15]),
    }


def generate_section(
    section_name: str,
    profile: Dict[str, Any],
    job: Dict[str, Any],
    feedback: Optional[str] = None
) -> str:
    """
    Generate a single resume section using LLM.
    
    Args:
        section_name: One of RESUME_SECTIONS (header, summary, skills, experience, education, publications)
        profile: User profile dictionary
        job: Job posting dictionary
        feedback: Optional feedback from critic for refinement
    
    Returns:
        Generated section content (cleaned of artifacts)
    """
    if section_name not in SECTION_PROMPTS:
        raise ValueError(f"Unknown section: {section_name}. Must be one of {RESUME_SECTIONS}")
    
    # Extract data for prompt
    data = _extract_section_data(profile, job)
    
    # Add feedback if provided
    feedback_section = ""
    if feedback:
        feedback_section = f"""
FEEDBACK FROM PREVIOUS ATTEMPT (address these issues):
{feedback}
"""
    data["feedback_section"] = feedback_section
    
    # Format the section-specific prompt
    prompt = SECTION_PROMPTS[section_name].format(**data)
    
    logger.info(f"Generating section: {section_name}")
    
    raw_content = _call_ollama(prompt, temperature=0.3)
    content = _clean_template_artifacts(raw_content)
    
    return content


def generate_resume_by_sections(
    profile: Dict[str, Any],
    job: Dict[str, Any],
    existing_sections: Optional[Dict[str, str]] = None,
    sections_to_regenerate: Optional[List[str]] = None,
    feedback_by_section: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Generate resume section by section, optionally regenerating specific sections.
    
    Args:
        profile: User profile dictionary
        job: Job posting dictionary
        existing_sections: Previously generated sections to keep
        sections_to_regenerate: List of section names to regenerate (None = all)
        feedback_by_section: Dict mapping section name to feedback string
    
    Returns:
        Dict mapping section name to generated content
    """
    sections = existing_sections.copy() if existing_sections else {}
    feedback_by_section = feedback_by_section or {}
    
    # Determine which sections to generate
    if sections_to_regenerate is None:
        # Generate all sections
        sections_to_generate = RESUME_SECTIONS
    else:
        sections_to_generate = sections_to_regenerate
    
    logger.info(f"Generating sections: {sections_to_generate}")
    
    for section_name in sections_to_generate:
        feedback = feedback_by_section.get(section_name)
        sections[section_name] = generate_section(section_name, profile, job, feedback)
    
    return sections


def assemble_sections(sections: Dict[str, str]) -> str:
    """
    Assemble individual sections into a complete resume document.
    
    Args:
        sections: Dict mapping section name to content
    
    Returns:
        Complete resume content as a single string
    """
    parts = []
    
    for section_name in RESUME_SECTIONS:
        content = sections.get(section_name, "")
        if content and content.strip():
            # Ensure section has proper marker
            if not content.strip().startswith(f"[{section_name.upper()}]"):
                content = f"[{section_name.upper()}]\n{content}"
            parts.append(content.strip())
    
    return "\n\n".join(parts)
