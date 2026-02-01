"""
Resume Tools: Main tool functions for generating tailored resumes and cover letters.

Integrates document generation, critique, and PDF output with iterative refinement.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from google.adk.tools import FunctionTool

from .profile_store import get_store
from .job_cache import get_cache
from .document_generator import generate_resume_content, generate_cover_letter_content
from .document_critic import critique_document, format_critique_feedback, CritiqueResult
from .pdf_generator import generate_resume_pdf, generate_cover_letter_pdf, validate_single_page

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_MAX_ITERATIONS = 5
PASS_THRESHOLD = 75
FACT_THRESHOLD = 100
GRAMMAR_THRESHOLD = 90  # Grammar must be near-perfect

# Module-level setting that can be modified
_max_iterations = DEFAULT_MAX_ITERATIONS


def set_max_iterations(value: int):
    """Set the maximum number of generation iterations.
    
    Args:
        value: Number of iterations (must be >= 1)
    
    Raises:
        ValueError: If value is less than 1
    """
    if value < 1:
        raise ValueError(f"max_iterations must be >= 1, got {value}")
    global _max_iterations
    _max_iterations = value


def get_max_iterations() -> int:
    """Get the current maximum iterations setting."""
    return _max_iterations


def _get_profile_and_job(job_id: str, profile_id: str = "") -> tuple:
    """Helper to fetch profile and job data."""
    store = get_store()
    cache = get_cache()
    
    # Get profile
    profiles = store.list_profiles()
    if not profiles:
        raise ValueError("No profiles found. Please create a profile first.")
    
    if profile_id:
        profile = store.get(profile_id)
    else:
        profile = store.get(profiles[0].get("id"))
    
    if not profile:
        raise ValueError(f"Profile not found: {profile_id}")
    
    # Normalize skills if needed
    if profile.get("skills") and isinstance(profile["skills"][0], dict):
        pass  # Already normalized
    
    # Get job
    job = cache.get(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")
    
    return profile, job


def _run_generation_loop(
    doc_type: str,
    profile: Dict[str, Any],
    job: Dict[str, Any],
    max_iterations: int = None,
) -> tuple:
    """
    Run the generation-critique loop until quality thresholds are met.
    
    Args:
        doc_type: "resume" or "cover_letter"
        profile: User profile dictionary
        job: Job posting dictionary
        max_iterations: Maximum iterations (uses global setting if not specified)
    
    Returns:
        Tuple of (content, final_critique)
    """
    if max_iterations is None:
        max_iterations = get_max_iterations()
    
    feedback = None
    content = None
    critique = None
    
    for iteration in range(max_iterations):
        logger.info(f"Generation iteration {iteration + 1}/{max_iterations}")
        
        # Generate document
        if doc_type == "resume":
            result = generate_resume_content(profile, job, feedback)
        else:
            result = generate_cover_letter_content(profile, job, feedback)
        
        content = result["content"]
        
        # Critique document
        critique = critique_document(content, doc_type, profile, job)
        
        logger.info(
            f"Critique scores - Fact: {critique.fact_score}%, "
            f"Keyword: {critique.keyword_score}%, "
            f"ATS: {critique.ats_score}%, "
            f"Grammar: {critique.grammar_score}%, "
            f"Overall: {critique.overall_score}%"
        )
        
        # Check if passed all thresholds
        if critique.passed:
            logger.info(f"Document passed all quality checks on iteration {iteration + 1}")
            break
        
        # Build feedback for next iteration
        feedback = format_critique_feedback(critique)
        logger.info(f"Feedback for regeneration: {feedback[:200]}...")
    
    if not critique.passed:
        logger.warning(
            f"Document did not pass all checks after {max_iterations} iterations. "
            f"Proceeding with best effort."
        )
        if critique.fabricated_facts:
            logger.warning(f"Unverified facts remain: {critique.fabricated_facts}")
    
    return content, critique


def generate_resume(job_id: str, profile_id: str = "") -> str:
    """
    Generate a tailored resume PDF for a specific job.
    
    Uses iterative refinement with LLM generation and critique until quality
    thresholds are met (or max iterations reached). If the PDF exceeds one page,
    the content is regenerated with feedback to be more concise.
    
    Args:
        job_id: ID of the job to generate resume for
        profile_id: Profile ID (optional, uses first profile if not specified)
    
    Returns:
        TOON-formatted result with PDF path and quality scores
    """
    try:
        profile, job = _get_profile_and_job(job_id, profile_id)
        
        company = job.get("company", "Unknown")
        job_title = job.get("title", "Unknown")
        
        logger.info(f"Generating resume for {job_title} at {company}")
        
        # Page fitting loop - regenerate if not single page
        max_page_attempts = 3
        content = None
        critique = None
        pdf_path = None
        is_single_page = False
        page_count = 0
        page_feedback = None
        
        for page_attempt in range(max_page_attempts):
            # Run generation loop (with page feedback if not first attempt)
            if page_feedback:
                logger.info(f"Page fitting attempt {page_attempt + 1}: regenerating with length feedback")
                # Generate with page fitting feedback
                gen_result = generate_resume_content(profile, job, feedback=page_feedback)
                content = gen_result["content"]
                # Critique the new content
                critique = critique_document(content, "resume", profile, job)
            else:
                content, critique = _run_generation_loop("resume", profile, job)
            
            # Generate PDF
            pdf_path = generate_resume_pdf(
                content,
                company,
                profile.get("name", "Candidate")
            )
            
            # Validate single page
            is_single_page, page_count, page_msg = validate_single_page(pdf_path)
            
            if is_single_page:
                logger.info(f"Resume fits on single page (attempt {page_attempt + 1})")
                break
            else:
                logger.warning(f"Resume has {page_count} pages (attempt {page_attempt + 1}), regenerating...")
                page_feedback = (
                    f"CRITICAL: The generated resume is {page_count} pages but MUST be exactly 1 page. "
                    f"REDUCE content significantly:\n"
                    f"- Use shorter bullet points (max 15-20 words each)\n"
                    f"- Keep only 2-3 bullet points per job\n"
                    f"- Remove less impactful achievements\n"
                    f"- Use concise language, avoid redundancy\n"
                    f"- Limit skills to 10-12 most relevant\n"
                    f"- Keep summary to 2 sentences maximum"
                )
        
        # Format response
        result = f"""[resume_generation]
status: {'success' if critique.passed and is_single_page else 'completed_with_warnings'}
pdf_path: {pdf_path}
job_title: {job_title}
company: {company}
page_fitting_attempts: {page_attempt + 1}

[quality_scores]
fact_verification: {critique.fact_score}%
keyword_match: {critique.keyword_score}%
ats_compatibility: {critique.ats_score}%
overall: {critique.overall_score}%
length_compliant: {critique.length_compliant}
single_page: {is_single_page}
page_count: {page_count}

[verification]
verified_facts: {len(critique.verified_facts)}
unverified_facts: {len(critique.unverified_facts)}
fabricated_facts: {len(critique.fabricated_facts)}
"""
        
        warnings = []
        if critique.fabricated_facts:
            warnings.append(f"fabricated_facts: {', '.join(critique.fabricated_facts)}")
        if not is_single_page:
            warnings.append(f"multi_page: Resume has {page_count} pages after {max_page_attempts} attempts (should be 1)")
        
        if warnings:
            result += "\n[warnings]\n" + "\n".join(warnings)
        
        if critique.suggestions:
            result += f"\n[suggestions]\n" + "\n".join(f"- {s}" for s in critique.suggestions[:3])
        
        return result
        
    except Exception as e:
        logger.error(f"Resume generation failed: {e}")
        return f"""[error]
message: {str(e)}
"""


def generate_cover_letter(job_id: str, profile_id: str = "") -> str:
    """
    Generate a tailored cover letter PDF for a specific job.
    
    Uses iterative refinement with LLM generation and critique until quality
    thresholds are met (or max iterations reached).
    
    Args:
        job_id: ID of the job to generate cover letter for
        profile_id: Profile ID (optional, uses first profile if not specified)
    
    Returns:
        TOON-formatted result with PDF path and quality scores
    """
    try:
        profile, job = _get_profile_and_job(job_id, profile_id)
        
        company = job.get("company", "Unknown")
        job_title = job.get("title", "Unknown")
        
        logger.info(f"Generating cover letter for {job_title} at {company}")
        
        # Run generation loop
        content, critique = _run_generation_loop("cover_letter", profile, job)
        
        # Build contact info from profile (email and phone for header)
        contact_parts = []
        if profile.get("email"):
            contact_parts.append(profile["email"])
        if profile.get("phone"):
            contact_parts.append(profile["phone"])
        contact_info = "  |  ".join(contact_parts) if contact_parts else ""
        
        # Generate PDF
        pdf_path = generate_cover_letter_pdf(
            content,
            company,
            profile.get("name", "Candidate"),
            contact_info=contact_info
        )
        
        # Format response
        result = f"""[cover_letter_generation]
status: {'success' if critique.passed else 'completed_with_warnings'}
pdf_path: {pdf_path}
job_title: {job_title}
company: {company}

[quality_scores]
fact_verification: {critique.fact_score}%
keyword_match: {critique.keyword_score}%
ats_compatibility: {critique.ats_score}%
overall: {critique.overall_score}%
length_compliant: {critique.length_compliant}
word_count_feedback: {critique.length_feedback}

[verification]
verified_facts: {len(critique.verified_facts)}
unverified_facts: {len(critique.unverified_facts)}
fabricated_facts: {len(critique.fabricated_facts)}
"""
        
        if critique.fabricated_facts:
            result += f"\n[warnings]\nfabricated_facts: {', '.join(critique.fabricated_facts)}"
        
        if critique.suggestions:
            result += f"\n[suggestions]\n" + "\n".join(f"- {s}" for s in critique.suggestions[:3])
        
        return result
        
    except Exception as e:
        logger.error(f"Cover letter generation failed: {e}")
        return f"""[error]
message: {str(e)}
"""


def generate_application_package(job_id: str, profile_id: str = "") -> str:
    """
    Generate both resume and cover letter PDFs for a specific job.
    
    Args:
        job_id: ID of the job to generate documents for
        profile_id: Profile ID (optional, uses first profile if not specified)
    
    Returns:
        TOON-formatted result with both PDF paths and quality scores
    """
    results = []
    
    # Generate resume
    resume_result = generate_resume(job_id, profile_id)
    results.append("[RESUME]")
    results.append(resume_result)
    
    # Generate cover letter
    cover_result = generate_cover_letter(job_id, profile_id)
    results.append("\n[COVER_LETTER]")
    results.append(cover_result)
    
    return "\n".join(results)


# Register as ADK tools
generate_resume_tool = FunctionTool(func=generate_resume)
generate_cover_letter_tool = FunctionTool(func=generate_cover_letter)
generate_application_package_tool = FunctionTool(func=generate_application_package)
