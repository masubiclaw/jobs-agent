"""Application Designer - Creates complete job applications (resume + cover letter) in parallel."""

import logging

from google.adk.agents import LlmAgent, ParallelAgent, Agent
from google.adk.tools import google_search, FunctionTool

from .resume_prompt import RESUME_DESIGNER_PROMPT
from .cover_letter_prompt import COVER_LETTER_WRITER_PROMPT
from ...tools.pdf_tools import (
    generate_resume_pdf_tool,
    generate_cover_letter_pdf_tool,
    list_generated_pdfs,
    is_pdf_generation_available,
    get_resume_template_presets,
)

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-pro"

# =============================================================================
# PDF Generation Tools as FunctionTools
# =============================================================================

def generate_resume_pdf(
    name: str,
    contact_info: str,
    title: str,
    summary: str,
    sections_json: str,
    output_filename: str = ""
) -> str:
    """
    Generate a professional resume PDF.
    
    Args:
        name: Full name for header (e.g., "John Smith")
        contact_info: Contact line (e.g., "Seattle, WA • john@email.com • linkedin.com/in/john")
        title: Professional title (e.g., "Senior Software Engineer | AI & Cloud")
        summary: Professional summary paragraph
        sections_json: JSON array of [section_name, content] where content is array of strings/bullet arrays
        output_filename: Custom filename (optional, auto-generated if empty)
    
    Returns:
        JSON with success, filepath, filename, or error
    
    Example sections_json:
        '[["Experience", ["<b>Company — Title</b> | 2020–Present", ["Bullet 1", "Bullet 2"]]], ["Skills", [["Python", "JavaScript"]]]]'
    """
    return generate_resume_pdf_tool(name, contact_info, title, summary, sections_json, output_filename or None)


def generate_cover_letter_pdf(
    name: str,
    contact_info: str,
    body_paragraphs_json: str,
    target_company: str = "",
    target_role: str = "",
    salutation: str = "Dear Hiring Manager,",
    closing: str = "Sincerely,",
    output_filename: str = ""
) -> str:
    """
    Generate a professional cover letter PDF.
    
    Args:
        name: Full name
        contact_info: Contact line
        body_paragraphs_json: JSON array of paragraph strings (e.g., '["First paragraph...", "Second paragraph..."]')
        target_company: Company name (used in filename)
        target_role: Role title (for reference)
        salutation: Opening salutation (default: "Dear Hiring Manager,")
        closing: Closing phrase (default: "Sincerely,")
        output_filename: Custom filename (optional)
    
    Returns:
        JSON with success, filepath, filename, or error
    """
    return generate_cover_letter_pdf_tool(
        name, contact_info, body_paragraphs_json,
        target_company or None, target_role or None,
        salutation, closing, output_filename or None
    )


def list_pdfs() -> dict:
    """
    List all generated PDF files.
    
    Returns:
        List of PDFs with filename, filepath, created date, size
    """
    import json
    pdfs = list_generated_pdfs()
    return {"pdfs": pdfs, "count": len(pdfs)}


def check_pdf_available() -> dict:
    """
    Check if PDF generation is available (ReportLab installed).
    
    Returns:
        Status of PDF generation capability
    """
    available = is_pdf_generation_available()
    return {
        "available": available,
        "message": "PDF generation ready" if available else "Install reportlab: pip install reportlab"
    }


def get_template_presets() -> dict:
    """
    Get predefined resume template configurations.
    
    Returns:
        Dictionary of template presets (professional, compact, leadership, technical)
    """
    return get_resume_template_presets()

# =============================================================================
# Resume Writer Agent
# =============================================================================

resume_writer_agent = LlmAgent(
    model=MODEL,
    name="resume_writer_agent",
    description=(
        "Creates compelling, optimized resumes tailored to specific roles "
        "and job postings. Focuses on quantifiable achievements, keyword "
        "optimization, and creating a standout narrative. Maintains strict "
        "truthfulness with guard rails. Can generate PDF output."
    ),
    instruction=RESUME_DESIGNER_PROMPT,
    output_key="resume_output",
    tools=[
        google_search,
        FunctionTool(func=generate_resume_pdf),
        FunctionTool(func=check_pdf_available),
        FunctionTool(func=get_template_presets),
    ],
)

logger.info("   ✅ Resume Writer Agent initialized (with PDF generation)")

# =============================================================================
# Cover Letter Agent
# =============================================================================

cover_letter_agent = LlmAgent(
    model="gemini-2.5-flash",  # Faster for cover letters
    name="cover_letter_agent",
    description=(
        "Creates tailored, compelling cover letters based on user profile, "
        "job posting, and company research. Uses story-driven approach with "
        "achievement highlights and company-specific alignment. Can generate PDF output."
    ),
    instruction=COVER_LETTER_WRITER_PROMPT,
    output_key="cover_letter_output",
    tools=[
        google_search,
        FunctionTool(func=generate_cover_letter_pdf),
        FunctionTool(func=check_pdf_available),
    ],
)

logger.info("   ✅ Cover Letter Agent initialized (with PDF generation)")

# =============================================================================
# Application Designer - Parallel Orchestration
# =============================================================================

# Creates both resume and cover letter simultaneously
parallel_document_creation = ParallelAgent(
    name="parallel_document_creation",
    description="Creates resume and cover letter in parallel for faster application preparation",
    sub_agents=[
        resume_writer_agent,
        cover_letter_agent,
    ],
)

# Main Application Designer Agent - Orchestrates the full application workflow
application_designer_agent = Agent(
    model=MODEL,
    name="application_designer_agent",
    description=(
        "Creates complete job applications including tailored resume and cover letter. "
        "Runs document creation in parallel for efficiency. Includes storage for "
        "resume versions, cover letters, templates, and design instructions. "
        "Can generate professional PDF output. Enforces strict truthfulness guard rails."
    ),
    instruction="""
role: application_designer
version: 3.0

identity:
  name: Application Designer
  specialty: Complete job application packages (resume + cover letter) with PDF generation
  approach: Parallel creation with unified narrative and strict truthfulness verification

inputs:
  required:
    - user_profile: candidate background, skills, achievements (SOURCE OF TRUTH)
    - target_role: position applying for
    - job_posting: full job description (REQUIRED for 115% boost)
  optional:
    - target_company: specific company name
    - company_research: culture, values, mission
    - tone_preference: formal/conversational/enthusiastic
    - resume_version_name: name for this resume version
    - generate_pdf: true/false - whether to output PDF files
    - template_preference: professional/compact/leadership/technical/custom

# =============================================================================
# CRITICAL GUARD RAILS: SOURCE TRUTHFULNESS VERIFICATION
# =============================================================================
guard_rails:
  CRITICAL_RULES:
    - NEVER fabricate experiences, skills, jobs, or achievements
    - NEVER invent metrics or numbers not provided in user_profile
    - NEVER add certifications user doesn't have
    - NEVER embellish job titles or responsibilities beyond source
    - NEVER create fictional companies, projects, or references
    - ALL claims MUST be traceable to user_profile source
  
  VERIFICATION_PROCESS:
    step_1: "Extract all claims from user_profile (skills, experience, achievements)"
    step_2: "Map each resume/cover letter statement back to source evidence"
    step_3: "Flag any statement that cannot be traced to source"
    step_4: "Generate truthfulness audit report"
    step_5: "REJECT any content that fails verification"
  
  ALLOWED_ENHANCEMENTS:
    - Reframe existing achievements with stronger action verbs
    - Reorganize content to highlight relevant experience
    - Improve formatting and structure
    - Add context that clarifies (not inflates) achievements
    - Suggest certifications user COULD pursue (marked as "Recommended")
  
  FLAGGING_REQUIRED:
    - "[NEEDS VERIFICATION]" - for any claim needing user confirmation
    - "[ESTIMATED]" - for any estimated metrics (must be confirmed)
    - "[RECOMMENDED TO ADD]" - for suggestions not in source profile

workflow:
  1_load_instructions:
    - Check for active design instructions/guard rails from storage
    - Load default or custom resume template
    - Validate all requirements before proceeding
  
  2_analyze_inputs:
    - Extract key requirements from job posting
    - Identify company values and culture signals
    - Determine best resume format and cover letter tone
    - VERIFY user_profile contains necessary source evidence
  
  3_parallel_creation:
    - Use parallel_document_creation to create both simultaneously
    - Resume: Tailored to job requirements with VERIFIED achievements only
    - Cover Letter: Story-driven with company alignment using VERIFIED stories
  
  4_truthfulness_audit:
    - Verify ALL claims trace back to user_profile
    - Flag any unverified statements
    - Generate audit report showing source mapping
    - REJECT content with fabricated claims
  
  5_ensure_consistency:
    - Verify resume and cover letter tell same narrative
    - Check achievements in cover letter match resume exactly
    - Ensure consistent tone and messaging
  
  6_generate_pdfs:
    - If generate_pdf=true, create professional PDF files
    - Use template formatting preferences
    - Store PDF paths in output
  
  7_storage:
    - Save resume version with descriptor and truthfulness score
    - Save cover letter with metadata and source references
    - Link both to job posting if provided

storage_integration:
  resume_templates:
    - template_name: formatting style name
    - styles: font sizes, margins, spacing
    - sections_order: section arrangement
    - is_default: default template flag
  
  design_instructions:
    - guard_rails: truthfulness rules (MUST CHECK)
    - requirements: formatting requirements
    - content_rules: content guidelines
  
  resume_versions:
    - version_name: descriptive name for this version
    - version_descriptor: what makes this version unique
    - target_role: role optimized for
    - truthfulness_score: audit result
    - pdf_path: generated PDF location (if created)
    - is_master: if this is base resume
  
  cover_letters:
    - target_role: position title
    - target_company: company name
    - key_highlights: achievements emphasized (must match source)
    - tone: selected tone
    - pdf_path: generated PDF location (if created)

pdf_generation:
  capabilities:
    - generate_resume_pdf: Create professional resume PDF
    - generate_cover_letter_pdf: Create professional cover letter PDF
    - list_pdfs: List all generated PDFs
    - check_pdf_available: Verify PDF generation ready
    - get_template_presets: Get predefined formatting templates

DISPLAY_FORMAT: |
  ╔══════════════════════════════════════════════════════════════════╗
  ║                  📦 APPLICATION PACKAGE COMPLETE                  ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║ Target: [Role] @ [Company]                                       ║
  ║ Documents Created: Resume ✓ | Cover Letter ✓                     ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║ 🛡️ TRUTHFULNESS AUDIT:                                           ║
  ║    Source-verified claims: [X]/[Y]                               ║
  ║    Items needing verification: [X]                               ║
  ║    Fabrication check: [PASSED ✓ / FAILED ❌]                      ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║ 📄 RESUME VERSION:                                               ║
  ║    Name: [version_name]                                          ║
  ║    Descriptor: [what makes this unique]                          ║
  ║    Optimization Score: [XX]/100                                  ║
  ║    PDF Generated: [filepath or "Not requested"]                  ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║ ✉️ COVER LETTER:                                                  ║
  ║    Tone: [formal/conversational/enthusiastic]                    ║
  ║    Hook Strategy: [opening approach used]                        ║
  ║    Key Stories: [achievements highlighted]                       ║
  ║    PDF Generated: [filepath or "Not requested"]                  ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║ 🔗 NARRATIVE CONSISTENCY: [Verified ✓ / Needs Alignment ⚠️]      ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║ 💾 STORAGE:                                                      ║
  ║    Resume saved: [ID]                                            ║
  ║    Cover letter saved: [ID]                                      ║
  ╚══════════════════════════════════════════════════════════════════╝

output:
  - resume_content: complete tailored resume (verified)
  - cover_letter_content: complete tailored cover letter (verified)
  - resume_version_id: storage ID
  - cover_letter_id: storage ID
  - truthfulness_audit: verification results with source mapping
  - consistency_check: narrative consistency results
  - pdf_paths: {resume: filepath, cover_letter: filepath} (if generated)
""",
    output_key="application_output",
    sub_agents=[parallel_document_creation],
    tools=[
        google_search,
        FunctionTool(func=generate_resume_pdf),
        FunctionTool(func=generate_cover_letter_pdf),
        FunctionTool(func=list_pdfs),
        FunctionTool(func=check_pdf_available),
        FunctionTool(func=get_template_presets),
    ],
)

logger.info("✅ Application Designer Agent initialized (parallel resume + cover letter with PDF generation)")

