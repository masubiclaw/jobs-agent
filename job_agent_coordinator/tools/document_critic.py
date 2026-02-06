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
OLLAMA_BASE_URL = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:12b")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 120))

# Length constraints
RESUME_MIN_WORDS = 400  # Resume should have enough content to fill a page
RESUME_MAX_WORDS = 600
COVER_LETTER_MIN_WORDS = 200
COVER_LETTER_MAX_WORDS = 400

# Template artifact patterns that indicate incomplete generation
# Keep in sync with TEMPLATE_ARTIFACTS in document_generator.py
# Note: Simple section markers like [OPENING], [DATE] are NOT artifacts - they're valid
ARTIFACT_PATTERNS = [
    # Section markers WITH instructions (bad - should have been replaced)
    r'\[OPENING\s+-\s+[^\]]+\]',      # [OPENING - 2-3 sentences, ~50 words]
    r'\[BODY PARAGRAPH \d+\s+-\s+[^\]]+\]',  # [BODY PARAGRAPH 1 - 3-4 sentences]
    r'\[CLOSING\s+-\s+[^\]]+\]',      # [CLOSING - 2-3 sentences]
    # Placeholder patterns (bad - LLM should have filled these in)
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


def _check_for_markdown(content: str) -> Tuple[bool, List[str]]:
    """
    Check if content contains markdown formatting that should have been cleaned.
    
    Detects:
    - **bold** and __bold__
    - *italic* and _italic_ (but not underscores in words)
    
    Args:
        content: Content to check
    
    Returns:
        Tuple of (has_markdown, list of found markdown patterns)
    """
    if not content:
        return False, []
    
    found = []
    
    # Check for bold markers
    bold_double = re.findall(r'\*\*[^*]+\*\*', content)
    bold_under = re.findall(r'__[^_]+__', content)
    found.extend(bold_double)
    found.extend(bold_under)
    
    # Check for italic markers (standalone, not mid-word underscores)
    italic_star = re.findall(r'(?<!\*)\*[^*]+\*(?!\*)', content)
    italic_under = re.findall(r'(?<!\w)_[^_]+_(?!\w)', content)
    found.extend(italic_star)
    found.extend(italic_under)
    
    return bool(found), found


# Problematic Unicode characters that should have been sanitized
PROBLEMATIC_CHARACTERS = {
    '\u2018': "left single quote '",
    '\u2019': "right single quote '", 
    '\u201C': 'left double quote "',
    '\u201D': 'right double quote "',
    '\u2013': 'en-dash –',
    '\u2014': 'em-dash —',
    '\u2026': 'ellipsis …',
    '\u00A0': 'non-breaking space',
    '\u2022': 'bullet •',
}


def _check_for_bad_characters(content: str) -> Tuple[bool, List[str]]:
    """
    Check if content contains problematic Unicode characters.
    
    These characters can cause display issues in PDFs and should be
    replaced with ASCII equivalents.
    
    Args:
        content: Content to check
    
    Returns:
        Tuple of (has_bad_chars, list of found character descriptions)
    """
    if not content:
        return False, []
    
    found = []
    for char, description in PROBLEMATIC_CHARACTERS.items():
        if char in content:
            count = content.count(char)
            found.append(f"{description} (×{count})")
    
    return bool(found), found


def _check_paragraph_structure(content: str, doc_type: str) -> Tuple[bool, str]:
    """
    Check if document has proper paragraph structure.
    
    For cover letters, ensures multiple paragraphs exist (not a single block).
    
    Args:
        content: Document content
        doc_type: "resume" or "cover_letter"
    
    Returns:
        Tuple of (is_valid, feedback message)
    """
    if doc_type != "cover_letter":
        return True, "Structure check only applies to cover letters"
    
    if not content:
        return False, "Cover letter content is empty"
    
    # Count paragraphs by looking for section markers or double newlines
    # Check for section markers
    has_opening = bool(re.search(r'\[OPENING\]', content, re.IGNORECASE))
    has_body1 = bool(re.search(r'\[BODY PARAGRAPH 1\]', content, re.IGNORECASE))
    has_body2 = bool(re.search(r'\[BODY PARAGRAPH 2\]', content, re.IGNORECASE))
    has_closing = bool(re.search(r'\[CLOSING\]', content, re.IGNORECASE))
    
    section_count = sum([has_opening, has_body1, has_body2, has_closing])
    
    if section_count >= 3:
        return True, f"Cover letter has {section_count} sections (good structure)"
    
    # Fallback: check for paragraph breaks (double newlines)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and len(p.strip()) > 50]
    
    if len(paragraphs) >= 3:
        return True, f"Cover letter has {len(paragraphs)} paragraphs (good structure)"
    
    return False, f"Cover letter appears to have only {max(section_count, len(paragraphs))} section(s). Should have at least 3 distinct paragraphs (opening, body, closing)."


@dataclass
class SectionCritiqueResult:
    """Result of critiquing a single resume section."""
    section_name: str
    passed: bool
    score: int  # 0-100
    issues: List[str]
    suggestions: List[str]
    has_artifacts: bool = False
    has_markdown: bool = False
    has_bad_chars: bool = False
    dates_valid: bool = True
    invalid_dates: Optional[List[str]] = None
    grammar_score: int = 100
    grammar_issues: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.invalid_dates is None:
            self.invalid_dates = []
        if self.grammar_issues is None:
            self.grammar_issues = []


# Section-specific validation rules
SECTION_RULES = {
    "header": {
        "required_fields": ["name"],
        "max_words": 50,
        "checks": ["contact_info_present"],
    },
    "summary": {
        "min_words": 30,
        "max_words": 80,
        "checks": ["no_fabrication", "relevant_to_job"],
    },
    "skills": {
        "min_items": 10,
        "max_items": 20,
        "checks": ["skills_from_profile"],
    },
    "experience": {
        "min_roles": 2,
        "max_roles": 5,
        "checks": ["dates_match_profile", "no_fabricated_metrics", "bullet_format", "action_verbs"],
    },
    "education": {
        "checks": ["matches_profile_exactly"],
    },
    "publications": {
        "checks": ["matches_profile_exactly"],
    },
}


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
    has_markdown: bool = False
    found_markdown: Optional[List[str]] = None
    structure_valid: bool = True
    structure_feedback: str = ""
    grammar_score: int = 100
    grammar_errors: Optional[List[Dict[str, str]]] = None
    grammar_feedback: str = ""
    dates_valid: bool = True
    invalid_dates: Optional[List[str]] = None
    has_bad_chars: bool = False
    found_bad_chars: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.found_artifacts is None:
            self.found_artifacts = []
        if self.found_markdown is None:
            self.found_markdown = []
        if self.grammar_errors is None:
            self.grammar_errors = []
        if self.invalid_dates is None:
            self.invalid_dates = []
        if self.found_bad_chars is None:
            self.found_bad_chars = []


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
        if word_count < RESUME_MIN_WORDS:
            return False, f"Resume too short: {word_count} words (min {RESUME_MIN_WORDS}). Add more detail to experience bullets, expand skills, or include additional relevant achievements."
        if word_count > RESUME_MAX_WORDS:
            return False, f"Resume too long: {word_count} words (max {RESUME_MAX_WORDS}). Remove less relevant content."
        return True, f"Resume length OK: {word_count} words ({RESUME_MIN_WORDS}-{RESUME_MAX_WORDS} target)"
    
    elif doc_type == "cover_letter":
        if word_count < COVER_LETTER_MIN_WORDS:
            return False, f"Cover letter too short: {word_count} words (min {COVER_LETTER_MIN_WORDS}). Add more substance."
        if word_count > COVER_LETTER_MAX_WORDS:
            return False, f"Cover letter too long: {word_count} words (max {COVER_LETTER_MAX_WORDS}). Be more concise."
        return True, f"Cover letter length OK: {word_count} words"
    
    return True, "Unknown document type"


# Month name mapping for date conversion
MONTH_NAMES = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
}


def _normalize_date(date_str: str) -> List[str]:
    """
    Convert profile date format to acceptable display formats.
    
    Args:
        date_str: Date like "2025-08", "present", "2023-10"
    
    Returns:
        List of acceptable formats: ["Aug 2025", "August 2025", "2025-08", "08/2025"]
    """
    if not date_str:
        return []
    
    date_lower = date_str.lower().strip()
    
    if date_lower == "present":
        return ["present", "Present", "current", "Current"]
    
    # Handle YYYY-MM format
    match = re.match(r'^(\d{4})-(\d{2})$', date_str)
    if match:
        year, month = match.groups()
        month_name = MONTH_NAMES.get(month, "")
        month_full = {
            "01": "January", "02": "February", "03": "March", "04": "April",
            "05": "May", "06": "June", "07": "July", "08": "August",
            "09": "September", "10": "October", "11": "November", "12": "December"
        }.get(month, "")
        
        return [
            f"{month_name} {year}",      # Aug 2025
            f"{month_full} {year}",       # August 2025
            f"{date_str}",                # 2025-08
            f"{month}/{year}",            # 08/2025
            f"{int(month)}/{year}",       # 8/2025
            year,                         # Just year is acceptable
        ]
    
    # Handle just year
    if re.match(r'^\d{4}$', date_str):
        return [date_str]
    
    return [date_str]


def _validate_dates(content: str, profile: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate that dates in the generated content match profile dates.
    
    Returns:
        Tuple of (all_valid, valid_dates, invalid_dates)
    """
    invalid_dates = []
    valid_dates = []
    
    # Build set of acceptable dates from profile
    acceptable_dates = set()
    profile_date_map = {}  # Map normalized -> original for feedback
    
    for exp in profile.get("experience", []):
        start = exp.get("start_date", "")
        end = exp.get("end_date", "")
        
        for date_str in [start, end]:
            if date_str:
                normalized = _normalize_date(date_str)
                for fmt in normalized:
                    acceptable_dates.add(fmt.lower())
                    profile_date_map[fmt.lower()] = date_str
    
    # Extract dates from content using common patterns
    # Match: "Aug 2025", "August 2025", "2025-08", "08/2025", "2025"
    date_patterns = [
        r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\b',
        r'\b(\d{1,2})/(\d{4})\b',
        r'\b(\d{4})-(\d{2})\b',
    ]
    
    found_dates = []
    
    # Find month-year dates
    for match in re.finditer(date_patterns[0], content, re.IGNORECASE):
        found_dates.append(match.group(0))
    
    # Find MM/YYYY dates
    for match in re.finditer(date_patterns[1], content):
        found_dates.append(match.group(0))
    
    # Find YYYY-MM dates
    for match in re.finditer(date_patterns[2], content):
        found_dates.append(match.group(0))
    
    # Check "Present" separately
    if re.search(r'\bpresent\b', content, re.IGNORECASE):
        found_dates.append("Present")
    
    # Validate each found date
    for date in found_dates:
        date_lower = date.lower()
        if date_lower in acceptable_dates or any(date_lower in ad for ad in acceptable_dates):
            valid_dates.append(date)
        else:
            # Check if it's a valid year from profile
            year_match = re.search(r'\d{4}', date)
            if year_match:
                year = year_match.group()
                if any(year in ad for ad in acceptable_dates):
                    valid_dates.append(date)
                    continue
            invalid_dates.append(date)
    
    return len(invalid_dates) == 0, valid_dates, invalid_dates


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
7. Achievement-focused bullet points (for resumes)

OUTPUT FORMAT (JSON):
{{
    "ats_score": 0-100,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}
"""


GRAMMAR_CHECK_PROMPT = """You are an expert grammar and writing quality checker. Analyze this {doc_type} for grammatical errors and writing quality issues.

DOCUMENT:
{document}

Check for these specific issues:
1. Subject-verb agreement errors (e.g., "team were" should be "team was")
2. Tense consistency (mixing past and present tense inappropriately)
3. Run-on sentences (multiple independent clauses without proper punctuation)
4. Comma splices (two independent clauses joined only by a comma)
5. Sentence fragments (incomplete sentences)
6. Pronoun reference errors (unclear what "it" or "they" refers to)
7. Awkward phrasing or unclear sentences
8. Missing articles (a, an, the)
9. Incorrect prepositions
10. Redundant or wordy phrases

Be STRICT - professional documents must have perfect grammar.

OUTPUT FORMAT (JSON):
{{
    "grammar_score": 0-100,
    "errors": [
        {{"error": "specific error text", "correction": "corrected text", "type": "error type"}}
    ],
    "error_count": number,
    "summary": "brief overall assessment"
}}

If there are NO errors, return grammar_score of 100 and empty errors array.
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
    
    # 0b. Check for markdown formatting that should have been cleaned
    has_markdown, found_markdown = _check_for_markdown(content)
    if has_markdown:
        logger.warning(f"Markdown formatting found in {doc_type}: {found_markdown[:3]}")
    
    # 0c. Check for problematic Unicode characters
    has_bad_chars, found_bad_chars = _check_for_bad_characters(content)
    if has_bad_chars:
        logger.warning(f"Problematic characters found in {doc_type}: {found_bad_chars[:3]}")
    
    # 0d. Check paragraph structure (for cover letters)
    structure_valid, structure_feedback = _check_paragraph_structure(content, doc_type)
    if not structure_valid:
        logger.warning(f"Structure issue in {doc_type}: {structure_feedback}")
    
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
    
    # 5. Grammar check via LLM
    grammar_prompt = GRAMMAR_CHECK_PROMPT.format(
        document=content,
        doc_type="resume" if doc_type == "resume" else "cover letter"
    )
    
    try:
        grammar_response = _call_ollama(grammar_prompt)
        # Extract JSON - handle nested objects
        json_match = re.search(r'\{[\s\S]*\}', grammar_response)
        if json_match:
            grammar_data = json.loads(json_match.group())
        else:
            grammar_data = {"grammar_score": 80, "errors": [], "error_count": 0, "summary": ""}
    except Exception as e:
        logger.warning(f"Grammar check parsing failed: {e}")
        grammar_data = {"grammar_score": 80, "errors": [], "error_count": 0, "summary": ""}
    
    grammar_score = grammar_data.get("grammar_score", 80)
    grammar_errors = grammar_data.get("errors", [])
    grammar_feedback = grammar_data.get("summary", "")
    
    if grammar_errors:
        logger.warning(f"Grammar issues found ({len(grammar_errors)}): {grammar_feedback}")
    
    # 5b. Date validation (for resumes)
    dates_valid = True
    invalid_dates = []
    if doc_type == "resume":
        dates_valid, valid_dates, invalid_dates = _validate_dates(content, profile)
        if invalid_dates:
            logger.warning(f"Invalid dates found: {invalid_dates}")
    
    # 6. Calculate overall score
    fact_score = fact_data.get("fact_score", 50)
    ats_score = ats_data.get("ats_score", 70)
    
    # If fabricated facts found, set fact_score to 0
    if fact_data.get("fabricated_facts"):
        fact_score = 0
    
    # Weighted average (facts are critical, grammar is important)
    # facts: 35%, keywords: 25%, ats: 20%, grammar: 20%
    overall_score = int(fact_score * 0.35 + keyword_score * 0.25 + ats_score * 0.20 + grammar_score * 0.20)
    
    # 7. Compile suggestions
    suggestions = ats_data.get("suggestions", [])
    if has_artifacts:
        suggestions.insert(0, f"CRITICAL: Remove template artifacts: {', '.join(found_artifacts[:3])}")
    if has_markdown:
        suggestions.insert(0, f"CRITICAL: Remove markdown formatting: {', '.join(found_markdown[:3])}. Use plain text only.")
    if has_bad_chars:
        suggestions.insert(0, f"CHARACTERS: Replace special characters with ASCII: {', '.join(found_bad_chars[:3])}. Use straight quotes, regular dashes.")
    if not structure_valid:
        suggestions.insert(0, f"STRUCTURE: {structure_feedback}")
    if grammar_score < 90:
        # Add specific grammar corrections as suggestions (grammar must be >= 90 to pass)
        if grammar_errors:
            error_examples = [f"'{e.get('error', '')}' → '{e.get('correction', '')}'" for e in grammar_errors[:3] if isinstance(e, dict)]
            if error_examples:
                suggestions.insert(0, f"GRAMMAR (CRITICAL - must fix to pass): {'; '.join(error_examples)}")
            else:
                suggestions.insert(0, f"GRAMMAR (CRITICAL): {grammar_feedback or 'Fix grammatical errors - must achieve 90%+ grammar score'}")
        else:
            suggestions.insert(0, f"GRAMMAR (CRITICAL): {grammar_feedback or 'Improve grammar and writing quality to 90%+'}")
    if missing_kw:
        suggestions.append(f"Add missing keywords: {', '.join(missing_kw[:5])}")
    if not length_ok:
        suggestions.insert(0, length_feedback)
    if invalid_dates:
        suggestions.insert(0, f"DATES (CRITICAL): Fix incorrect dates: {', '.join(invalid_dates)}. Use EXACT dates from profile (e.g., 'Aug 2025' for '2025-08').")
    
    # 8. Determine pass/fail (artifacts, markdown, dates, characters, and grammar issues cause failure)
    # Grammar must be >= 90 (near-perfect) for professional quality
    grammar_acceptable = grammar_score >= 90
    passed = (
        fact_score >= 100 and
        overall_score >= 75 and
        length_ok and
        not fact_data.get("fabricated_facts") and
        not has_artifacts and
        not has_markdown and
        not has_bad_chars and
        structure_valid and
        grammar_acceptable and
        dates_valid
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
        has_markdown=has_markdown,
        found_markdown=found_markdown,
        structure_valid=structure_valid,
        structure_feedback=structure_feedback,
        grammar_score=grammar_score,
        grammar_errors=grammar_errors,
        grammar_feedback=grammar_feedback,
        dates_valid=dates_valid,
        invalid_dates=invalid_dates,
        has_bad_chars=has_bad_chars,
        found_bad_chars=found_bad_chars,
    )


def format_critique_feedback(critique: CritiqueResult) -> str:
    """Format critique result as feedback string for regeneration."""
    feedback_parts = []
    
    if critique.has_artifacts:
        feedback_parts.append(f"CRITICAL: Remove template artifacts like {', '.join(critique.found_artifacts[:3])}. Generate actual content, not placeholders.")
    
    if critique.has_markdown:
        feedback_parts.append(f"CRITICAL: Remove markdown formatting like {', '.join(critique.found_markdown[:3])}. Use plain text only, no **bold** or *italic* markers.")
    
    if critique.has_bad_chars:
        feedback_parts.append(f"CHARACTERS: Replace special Unicode characters with ASCII equivalents. Found: {', '.join(critique.found_bad_chars[:3])}. Use straight quotes (' and \"), regular dashes (-), and standard periods (...).")
    
    if not critique.structure_valid:
        feedback_parts.append(f"STRUCTURE: {critique.structure_feedback}")
    
    if critique.fabricated_facts:
        feedback_parts.append(f"CRITICAL: Remove fabricated facts: {', '.join(critique.fabricated_facts)}")
    
    # Date feedback (CRITICAL for resumes)
    if not critique.dates_valid and critique.invalid_dates:
        feedback_parts.append(f"DATES (CRITICAL): These dates are WRONG and not in profile: {', '.join(critique.invalid_dates)}. Use ONLY exact dates from profile, formatted as 'Mon YYYY' (e.g., 'Aug 2025' for profile date '2025-08').")
    
    # Grammar feedback with specific corrections (CRITICAL - must be >= 90 to pass)
    if critique.grammar_score < 90:
        grammar_feedback = f"GRAMMAR (CRITICAL - current score {critique.grammar_score}%, need 90%+): Fix these errors - "
        if critique.grammar_errors:
            corrections = []
            for err in critique.grammar_errors[:5]:
                if isinstance(err, dict) and err.get('error') and err.get('correction'):
                    corrections.append(f"'{err['error']}' should be '{err['correction']}'")
            if corrections:
                grammar_feedback += "; ".join(corrections)
            else:
                grammar_feedback += critique.grammar_feedback or "Rewrite with perfect grammar, no errors"
        else:
            grammar_feedback += critique.grammar_feedback or "Rewrite with perfect grammar, proper sentence structure"
        feedback_parts.append(grammar_feedback)
    
    if not critique.length_compliant:
        feedback_parts.append(f"LENGTH: {critique.length_feedback}")
    
    if critique.keyword_score < 70:
        feedback_parts.append(f"KEYWORDS: Low keyword match ({critique.keyword_score}%). Add more job-relevant keywords.")
    
    if critique.suggestions:
        # Filter out grammar suggestions since we handle them separately
        non_grammar_suggestions = [s for s in critique.suggestions if not s.startswith("GRAMMAR:")]
        if non_grammar_suggestions:
            feedback_parts.append(f"SUGGESTIONS: {'; '.join(non_grammar_suggestions[:3])}")
    
    return "\n".join(feedback_parts)


def _check_section_skills(content: str, profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate that skills in content are from the profile.
    
    Returns:
        Tuple of (all_valid, list of fabricated skills)
    """
    # Extract profile skills
    profile_skills = set()
    for skill in profile.get("skills", []):
        if isinstance(skill, dict):
            profile_skills.add(skill.get("name", "").lower())
        else:
            profile_skills.add(str(skill).lower())
    
    # Extract skills from content (assumes comma-separated after [SKILLS])
    content_lower = content.lower()
    skills_match = re.search(r'\[skills\]\s*\n?(.+?)(?:\n\n|\n\[|$)', content_lower, re.DOTALL)
    if not skills_match:
        return True, []
    
    skills_text = skills_match.group(1)
    content_skills = [s.strip() for s in skills_text.split(",") if s.strip()]
    
    fabricated = []
    for skill in content_skills:
        skill_clean = skill.strip().lower()
        # Check if any profile skill matches (partial match for variations)
        if not any(ps in skill_clean or skill_clean in ps for ps in profile_skills):
            fabricated.append(skill)
    
    return len(fabricated) == 0, fabricated


def _check_bullet_format(content: str) -> Tuple[bool, List[str]]:
    """
    Check if experience bullets start with action verbs.
    
    Returns:
        Tuple of (all_valid, list of problematic bullets)
    """
    # Common weak phrases to avoid
    weak_phrases = [
        "responsible for", "helped with", "worked on", "assisted",
        "was involved", "participated in", "handled"
    ]
    
    issues = []
    
    # Find all bullet points
    bullets = re.findall(r'^-\s+(.+)$', content, re.MULTILINE)
    
    for bullet in bullets:
        bullet_lower = bullet.lower()
        for phrase in weak_phrases:
            if bullet_lower.startswith(phrase):
                issues.append(f"Bullet starts with weak phrase: '{bullet[:50]}...'")
                break
    
    return len(issues) == 0, issues


def _check_contact_info(content: str, profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Check if header has contact info.
    
    Returns:
        Tuple of (has_contact, list of missing items)
    """
    missing = []
    content_lower = content.lower()
    
    name = profile.get("name", "").lower()
    email = profile.get("email", "").lower()
    phone = profile.get("phone", "")
    
    if name and name not in content_lower:
        missing.append("name")
    if email and email not in content_lower:
        missing.append("email")
    if phone and phone not in content:
        missing.append("phone")
    
    return len(missing) == 0, missing


def critique_section(
    section_name: str,
    content: str,
    profile: Dict[str, Any],
    job: Dict[str, Any]
) -> SectionCritiqueResult:
    """
    Critique a single resume section.
    
    Args:
        section_name: Name of section (header, summary, skills, etc.)
        content: Section content
        profile: User profile for fact verification
        job: Job posting for relevance check
    
    Returns:
        SectionCritiqueResult with score and issues
    """
    issues = []
    suggestions = []
    score = 100
    
    rules = SECTION_RULES.get(section_name, {})
    
    # 1. Check for artifacts
    has_artifacts, found_artifacts = _check_for_artifacts(content)
    if has_artifacts:
        issues.append(f"Template artifacts found: {', '.join(found_artifacts[:3])}")
        score -= 30
    
    # 2. Check for markdown
    has_markdown, found_markdown = _check_for_markdown(content)
    if has_markdown:
        issues.append(f"Markdown found: {', '.join(found_markdown[:3])}")
        score -= 20
    
    # 3. Check for bad characters
    has_bad_chars, found_bad_chars = _check_for_bad_characters(content)
    if has_bad_chars:
        issues.append(f"Bad characters: {', '.join(found_bad_chars[:3])}")
        score -= 10
    
    # 4. Word count checks
    word_count = len(content.split())
    if "min_words" in rules and word_count < rules["min_words"]:
        issues.append(f"Too short: {word_count} words (min {rules['min_words']})")
        suggestions.append(f"Expand {section_name} to at least {rules['min_words']} words")
        score -= 15
    if "max_words" in rules and word_count > rules["max_words"]:
        issues.append(f"Too long: {word_count} words (max {rules['max_words']})")
        suggestions.append(f"Reduce {section_name} to under {rules['max_words']} words")
        score -= 10
    
    # 5. Section-specific checks
    dates_valid = True
    invalid_dates = []
    grammar_score = 100
    grammar_issues = []
    
    checks = rules.get("checks", [])
    
    if "contact_info_present" in checks:
        has_contact, missing = _check_contact_info(content, profile)
        if not has_contact:
            issues.append(f"Missing contact info: {', '.join(missing)}")
            score -= 20
    
    if "skills_from_profile" in checks:
        skills_ok, fabricated = _check_section_skills(content, profile)
        if not skills_ok:
            issues.append(f"Skills not in profile: {', '.join(fabricated[:5])}")
            suggestions.append("Use only skills from the profile")
            score -= 25
    
    if "dates_match_profile" in checks:
        dates_valid, valid, invalid_dates = _validate_dates(content, profile)
        if not dates_valid:
            issues.append(f"Invalid dates: {', '.join(invalid_dates)}")
            suggestions.append("Use exact dates from profile (format: Mon YYYY)")
            score -= 25
    
    if "bullet_format" in checks or "action_verbs" in checks:
        bullets_ok, bullet_issues = _check_bullet_format(content)
        if not bullets_ok:
            issues.extend(bullet_issues[:3])
            suggestions.append("Start bullets with strong action verbs")
            score -= 15
    
    # Ensure score stays in valid range
    score = max(0, min(100, score))
    
    # Determine pass/fail
    passed = (
        score >= 70 and
        not has_artifacts and
        not has_markdown and
        dates_valid
    )
    
    return SectionCritiqueResult(
        section_name=section_name,
        passed=passed,
        score=score,
        issues=issues,
        suggestions=suggestions,
        has_artifacts=has_artifacts,
        has_markdown=has_markdown,
        has_bad_chars=has_bad_chars,
        dates_valid=dates_valid,
        invalid_dates=invalid_dates,
        grammar_score=grammar_score,
        grammar_issues=grammar_issues,
    )


def critique_resume_sections(
    sections: Dict[str, str],
    profile: Dict[str, Any],
    job: Dict[str, Any]
) -> Dict[str, SectionCritiqueResult]:
    """
    Critique all resume sections and return results per section.
    
    Args:
        sections: Dict mapping section name to content
        profile: User profile for fact verification
        job: Job posting for relevance check
    
    Returns:
        Dict mapping section name to SectionCritiqueResult
    """
    results = {}
    
    for section_name, content in sections.items():
        if content and content.strip():
            results[section_name] = critique_section(section_name, content, profile, job)
            logger.info(
                f"Section '{section_name}': score={results[section_name].score}, "
                f"passed={results[section_name].passed}"
            )
        else:
            # Empty section - may be OK (e.g., publications)
            results[section_name] = SectionCritiqueResult(
                section_name=section_name,
                passed=True,
                score=100,
                issues=[],
                suggestions=[],
            )
    
    return results


def format_section_feedback(critique: SectionCritiqueResult) -> str:
    """
    Format section critique result as feedback string for regeneration.
    
    Args:
        critique: SectionCritiqueResult to format
    
    Returns:
        Formatted feedback string
    """
    feedback_parts = []
    
    if critique.has_artifacts:
        feedback_parts.append("CRITICAL: Remove template artifacts - generate actual content")
    
    if critique.has_markdown:
        feedback_parts.append("CRITICAL: Remove markdown formatting (**bold**, *italic*)")
    
    if critique.has_bad_chars:
        feedback_parts.append("CHARACTERS: Use straight quotes and regular dashes only")
    
    if not critique.dates_valid and critique.invalid_dates:
        feedback_parts.append(f"DATES: Fix incorrect dates: {', '.join(critique.invalid_dates)}. Use exact profile dates.")
    
    if critique.issues:
        feedback_parts.append(f"ISSUES: {'; '.join(critique.issues[:3])}")
    
    if critique.suggestions:
        feedback_parts.append(f"SUGGESTIONS: {'; '.join(critique.suggestions[:3])}")
    
    return "\n".join(feedback_parts)


def identify_sections_from_feedback(critique: CritiqueResult) -> List[str]:
    """
    Identify which sections need to be regenerated based on whole-document critique.
    
    Analyzes the critique feedback to determine which sections are problematic.
    
    Args:
        critique: CritiqueResult from whole-document critique
    
    Returns:
        List of section names that need regeneration
    """
    sections_to_fix = []
    
    # Date issues -> experience section
    if not critique.dates_valid:
        if "experience" not in sections_to_fix:
            sections_to_fix.append("experience")
    
    # Grammar issues - check which sections they affect
    if critique.grammar_score < 90:
        # Grammar issues could be in any section, but most likely in summary/experience
        if "summary" not in sections_to_fix:
            sections_to_fix.append("summary")
        if "experience" not in sections_to_fix:
            sections_to_fix.append("experience")
    
    # Fabricated facts -> experience section (most likely)
    if critique.fabricated_facts:
        if "experience" not in sections_to_fix:
            sections_to_fix.append("experience")
        if "skills" not in sections_to_fix:
            sections_to_fix.append("skills")
    
    # Length issues
    if not critique.length_compliant:
        if "too short" in critique.length_feedback.lower():
            # Need more content in experience/summary
            if "experience" not in sections_to_fix:
                sections_to_fix.append("experience")
            if "summary" not in sections_to_fix:
                sections_to_fix.append("summary")
        elif "too long" in critique.length_feedback.lower():
            # Need to trim experience mostly
            if "experience" not in sections_to_fix:
                sections_to_fix.append("experience")
            if "skills" not in sections_to_fix:
                sections_to_fix.append("skills")
    
    # Keyword issues -> skills and summary
    if critique.keyword_score < 70:
        if "skills" not in sections_to_fix:
            sections_to_fix.append("skills")
        if "summary" not in sections_to_fix:
            sections_to_fix.append("summary")
    
    # If no specific sections identified, regenerate the most impactful ones
    if not sections_to_fix:
        sections_to_fix = ["experience", "summary"]
    
    return sections_to_fix
