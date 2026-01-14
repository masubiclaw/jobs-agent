"""Cover Letter Writer Agent - Creates tailored cover letters with PDF generation."""

import logging

from google.adk.agents import LlmAgent
from google.adk.tools import google_search, FunctionTool

from .prompt import COVER_LETTER_WRITER_PROMPT
from ...tools.pdf_tools import (
    generate_cover_letter_pdf_tool,
    is_pdf_generation_available,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PDF Generation Tool Wrapper
# =============================================================================

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
        contact_info: Contact line (e.g., "Seattle, WA • email@example.com • linkedin.com/in/name")
        body_paragraphs_json: JSON array of paragraph strings (e.g., '["First paragraph...", "Second..."]')
        target_company: Company name (used in filename)
        target_role: Role title (for reference)
        salutation: Opening salutation (default: "Dear Hiring Manager,")
        closing: Closing phrase (default: "Sincerely,")
        output_filename: Custom filename (optional, auto-generated if empty)
    
    Returns:
        JSON string with success, filepath, filename, or error
    """
    return generate_cover_letter_pdf_tool(
        name, contact_info, body_paragraphs_json,
        target_company or None, target_role or None,
        salutation, closing, output_filename or None
    )


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


cover_letter_writer_agent = LlmAgent(
    name="cover_letter_writer_agent",
    model="gemini-2.5-flash",
    description=(
        "Creates tailored, compelling cover letters based on user profile, "
        "job posting, and company research. Uses story-driven approach with "
        "achievement highlights and company-specific alignment. "
        "Can generate professional PDF output."
    ),
    instruction=COVER_LETTER_WRITER_PROMPT,
    output_key="cover_letter_output",
    tools=[
        google_search,  # For company research if needed
        FunctionTool(func=generate_cover_letter_pdf),
        FunctionTool(func=check_pdf_available),
    ],
)

logger.info("✅ Cover Letter Writer Agent initialized (with PDF generation)")

