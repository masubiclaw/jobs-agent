"""PDF generation tools for resumes and cover letters.

These tools enable agents to generate professional PDF documents
similar to the genPDF.py reference implementation.
"""

import logging
import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional reportlab import
try:
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        ListFlowable, ListItem, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not installed. PDF generation disabled. Install with: pip install reportlab")


# =============================================================================
# PDF Output Directory
# =============================================================================

def get_output_directory() -> str:
    """Get the directory for storing generated PDFs."""
    output_dir = os.path.join(
        os.path.expanduser("~"), ".job_agent_coordinator", "generated_pdfs"
    )
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


# =============================================================================
# Resume PDF Generation
# =============================================================================

def generate_resume_pdf(
    name: str,
    contact_info: str,
    title: str,
    summary: str,
    sections: list[tuple[str, list]],
    output_filename: Optional[str] = None,
    output_directory: Optional[str] = None
) -> dict:
    """
    Generate a professional resume PDF.
    
    Args:
        name: Full name for header
        contact_info: Contact line (location, email, LinkedIn, etc.)
        title: Professional title/headline
        summary: Professional summary paragraph
        sections: List of (section_title, content_list) tuples
                  Content can be strings (paragraphs) or lists (bullet points)
        output_filename: Custom filename (auto-generated if not provided)
        output_directory: Custom directory (uses default if not provided)
    
    Returns:
        dict with:
            - success: bool
            - filepath: str (path to generated PDF)
            - filename: str
            - error: str (if failed)
    
    Example sections format:
        [
            ("Experience", [
                "<b>Company — Title</b> | 2020–Present",
                ["Bullet point 1", "Bullet point 2"],
                "<b>Previous Company — Title</b> | 2018–2020",
                ["Achievement 1", "Achievement 2"]
            ]),
            ("Skills", [["Python", "JavaScript", "SQL"]]),
            ("Education", [["M.S. Computer Science — University"]])
        ]
    """
    if not REPORTLAB_AVAILABLE:
        return {
            "success": False,
            "filepath": None,
            "filename": None,
            "error": "ReportLab not installed. Install with: pip install reportlab"
        }
    
    try:
        # Generate filename with date
        date_str = datetime.now().strftime("%m%d%Y")
        safe_name = name.replace(" ", "_").replace(".", "")
        
        if output_filename:
            filename = output_filename if output_filename.endswith(".pdf") else f"{output_filename}.pdf"
        else:
            filename = f"{safe_name}_Resume_{date_str}.pdf"
        
        # Determine output path
        out_dir = output_directory or get_output_directory()
        filepath = os.path.join(out_dir, filename)
        
        # Create PDF
        _build_resume_pdf(filepath, name, contact_info, title, summary, sections)
        
        logger.info(f"✅ Generated resume PDF: {filepath}")
        return {
            "success": True,
            "filepath": filepath,
            "filename": filename,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to generate resume PDF: {e}")
        return {
            "success": False,
            "filepath": None,
            "filename": None,
            "error": str(e)
        }


def _build_resume_pdf(
    path: str,
    name: str,
    contact_info: str,
    title: str,
    summary: str,
    sections: list[tuple[str, list]]
):
    """Internal function to build the resume PDF using ReportLab."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Header", fontSize=18, spaceAfter=6))
    styles.add(ParagraphStyle(name="SubHeader", fontSize=11, spaceAfter=4, leading=13))
    styles.add(ParagraphStyle(name="Section", fontSize=11.5, spaceBefore=6, spaceAfter=4))
    styles.add(ParagraphStyle(name="Body", fontSize=10.3, leading=13.0, spaceAfter=3))
    styles.add(ParagraphStyle(name="Contact", fontSize=10, leading=12))

    doc = SimpleDocTemplate(
        path,
        pagesize=LETTER,
        rightMargin=40, leftMargin=40,
        topMargin=36, bottomMargin=36
    )

    elems = []

    # Header
    elems.append(Paragraph(f"<b>{name}</b>", styles["Header"]))
    elems.append(Paragraph(contact_info, styles["Contact"]))
    elems.append(Spacer(1, 6))
    elems.append(HRFlowable(width="100%", thickness=0.5, spaceBefore=4, spaceAfter=7))

    # Title + Summary
    elems.append(Paragraph(f"<b>{title}</b>", styles["SubHeader"]))
    elems.append(Paragraph(summary, styles["Body"]))

    # Sections
    for section_title, block in sections:
        elems.append(Spacer(1, 5))
        elems.append(HRFlowable(width="100%", thickness=0.5, spaceBefore=4, spaceAfter=5))
        elems.append(Paragraph(f"<b>{section_title}</b>", styles["Section"]))

        for item in block:
            if isinstance(item, str):
                elems.append(Paragraph(item, styles["Body"]))
            else:
                # List of bullet points
                elems.append(ListFlowable(
                    [ListItem(Paragraph(b, styles["Body"])) for b in item],
                    bulletType="bullet",
                    leftIndent=14
                ))
                elems.append(Spacer(1, 2))

    doc.build(elems)


# =============================================================================
# Cover Letter PDF Generation
# =============================================================================

def generate_cover_letter_pdf(
    name: str,
    contact_info: str,
    date_str: Optional[str] = None,
    recipient_info: Optional[str] = None,
    salutation: str = "Dear Hiring Manager,",
    body_paragraphs: list[str] = None,
    closing: str = "Sincerely,",
    output_filename: Optional[str] = None,
    output_directory: Optional[str] = None,
    target_company: Optional[str] = None,
    target_role: Optional[str] = None
) -> dict:
    """
    Generate a professional cover letter PDF.
    
    Args:
        name: Full name
        contact_info: Contact line (location, email, phone, etc.)
        date_str: Date for letter (auto-generated if not provided)
        recipient_info: Recipient name/title/company (optional)
        salutation: Opening salutation
        body_paragraphs: List of paragraph strings
        closing: Closing phrase
        output_filename: Custom filename
        output_directory: Custom directory
        target_company: Company name for filename
        target_role: Role for filename
    
    Returns:
        dict with success, filepath, filename, error
    """
    if not REPORTLAB_AVAILABLE:
        return {
            "success": False,
            "filepath": None,
            "filename": None,
            "error": "ReportLab not installed. Install with: pip install reportlab"
        }
    
    if not body_paragraphs:
        return {
            "success": False,
            "filepath": None,
            "filename": None,
            "error": "body_paragraphs is required"
        }
    
    try:
        # Generate filename
        file_date = datetime.now().strftime("%m%d%Y")
        safe_name = name.replace(" ", "_").replace(".", "")
        
        if output_filename:
            filename = output_filename if output_filename.endswith(".pdf") else f"{output_filename}.pdf"
        else:
            company_part = f"_{target_company.replace(' ', '_')}" if target_company else ""
            filename = f"{safe_name}_CoverLetter{company_part}_{file_date}.pdf"
        
        # Determine output path
        out_dir = output_directory or get_output_directory()
        filepath = os.path.join(out_dir, filename)
        
        # Create PDF
        letter_date = date_str or datetime.now().strftime("%B %d, %Y")
        _build_cover_letter_pdf(
            filepath, name, contact_info, letter_date,
            recipient_info, salutation, body_paragraphs, closing
        )
        
        logger.info(f"✅ Generated cover letter PDF: {filepath}")
        return {
            "success": True,
            "filepath": filepath,
            "filename": filename,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to generate cover letter PDF: {e}")
        return {
            "success": False,
            "filepath": None,
            "filename": None,
            "error": str(e)
        }


def _build_cover_letter_pdf(
    path: str,
    name: str,
    contact_info: str,
    date_str: str,
    recipient_info: Optional[str],
    salutation: str,
    body_paragraphs: list[str],
    closing: str
):
    """Internal function to build cover letter PDF."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Header", fontSize=14, spaceAfter=4))
    styles.add(ParagraphStyle(name="Contact", fontSize=10, leading=12))
    styles.add(ParagraphStyle(name="Date", fontSize=10, spaceBefore=12, spaceAfter=12))
    styles.add(ParagraphStyle(name="Recipient", fontSize=10, leading=13, spaceAfter=12))
    styles.add(ParagraphStyle(name="Body", fontSize=10.5, leading=14, spaceAfter=10))
    styles.add(ParagraphStyle(name="Closing", fontSize=10.5, spaceBefore=12))
    styles.add(ParagraphStyle(name="Signature", fontSize=10.5, spaceBefore=24))

    doc = SimpleDocTemplate(
        path,
        pagesize=LETTER,
        rightMargin=60, leftMargin=60,
        topMargin=50, bottomMargin=50
    )

    elems = []

    # Header with name and contact
    elems.append(Paragraph(f"<b>{name}</b>", styles["Header"]))
    elems.append(Paragraph(contact_info, styles["Contact"]))
    
    # Date
    elems.append(Paragraph(date_str, styles["Date"]))
    
    # Recipient info if provided
    if recipient_info:
        elems.append(Paragraph(recipient_info, styles["Recipient"]))
    
    # Salutation
    elems.append(Paragraph(salutation, styles["Body"]))
    elems.append(Spacer(1, 6))
    
    # Body paragraphs
    for paragraph in body_paragraphs:
        elems.append(Paragraph(paragraph, styles["Body"]))
    
    # Closing
    elems.append(Paragraph(closing, styles["Closing"]))
    elems.append(Paragraph(name, styles["Signature"]))

    doc.build(elems)


# =============================================================================
# Utility Functions
# =============================================================================

def list_generated_pdfs(directory: Optional[str] = None) -> list[dict]:
    """
    List all generated PDFs.
    
    Returns:
        List of dicts with filename, filepath, created, size
    """
    out_dir = directory or get_output_directory()
    pdfs = []
    
    if os.path.exists(out_dir):
        for f in os.listdir(out_dir):
            if f.endswith(".pdf"):
                filepath = os.path.join(out_dir, f)
                stat = os.stat(filepath)
                pdfs.append({
                    "filename": f,
                    "filepath": filepath,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "size_bytes": stat.st_size
                })
    
    return sorted(pdfs, key=lambda x: x["created"], reverse=True)


def delete_pdf(filepath: str) -> bool:
    """Delete a generated PDF."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Deleted PDF: {filepath}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete PDF: {e}")
        return False


def is_pdf_generation_available() -> bool:
    """Check if PDF generation is available."""
    return REPORTLAB_AVAILABLE


# =============================================================================
# Resume Template Presets
# =============================================================================

def get_resume_template_presets() -> dict:
    """
    Get predefined resume template configurations.
    
    These can be stored in the vector store for customization.
    """
    return {
        "professional": {
            "name": "Professional",
            "description": "Clean, traditional format suitable for corporate roles",
            "styles": {
                "header_size": 18,
                "section_size": 11.5,
                "body_size": 10.3,
                "line_spacing": 13.0,
                "margins": {"top": 36, "bottom": 36, "left": 40, "right": 40}
            },
            "sections_order": ["Summary", "Experience", "Skills", "Education", "Certifications"]
        },
        "compact": {
            "name": "Compact",
            "description": "Dense format for experienced professionals with lots of content",
            "styles": {
                "header_size": 16,
                "section_size": 10.5,
                "body_size": 9.5,
                "line_spacing": 11.5,
                "margins": {"top": 30, "bottom": 30, "left": 35, "right": 35}
            },
            "sections_order": ["Summary", "Experience", "Technical Skills", "Education"]
        },
        "leadership": {
            "name": "Leadership",
            "description": "Executive format emphasizing leadership and impact",
            "styles": {
                "header_size": 20,
                "section_size": 12,
                "body_size": 10.5,
                "line_spacing": 14.0,
                "margins": {"top": 40, "bottom": 40, "left": 45, "right": 45}
            },
            "sections_order": ["Executive Summary", "Leadership Experience", "Key Achievements", "Education & Credentials"]
        },
        "technical": {
            "name": "Technical",
            "description": "Format optimized for technical/engineering roles",
            "styles": {
                "header_size": 18,
                "section_size": 11.5,
                "body_size": 10,
                "line_spacing": 12.5,
                "margins": {"top": 36, "bottom": 36, "left": 40, "right": 40}
            },
            "sections_order": ["Summary", "Technical Skills", "Experience", "Projects", "Education", "Certifications"]
        }
    }


# =============================================================================
# FunctionTool Wrappers for Agent Use
# =============================================================================

def generate_resume_pdf_tool(
    name: str,
    contact_info: str,
    title: str,
    summary: str,
    sections_json: str,
    output_filename: Optional[str] = None
) -> str:
    """
    Tool wrapper for agents to generate resume PDFs.
    
    Args:
        name: Full name
        contact_info: Contact line
        title: Professional title
        summary: Summary paragraph
        sections_json: JSON string of sections list
        output_filename: Optional custom filename
    
    Returns:
        JSON string with result
    """
    import json
    
    try:
        sections = json.loads(sections_json)
        # Convert list format to tuple format
        sections_tuples = [(s[0], s[1]) for s in sections]
        
        result = generate_resume_pdf(
            name=name,
            contact_info=contact_info,
            title=title,
            summary=summary,
            sections=sections_tuples,
            output_filename=output_filename
        )
        return json.dumps(result)
    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON for sections: {e}"
        })


def generate_cover_letter_pdf_tool(
    name: str,
    contact_info: str,
    body_paragraphs_json: str,
    target_company: Optional[str] = None,
    target_role: Optional[str] = None,
    salutation: str = "Dear Hiring Manager,",
    closing: str = "Sincerely,",
    output_filename: Optional[str] = None
) -> str:
    """
    Tool wrapper for agents to generate cover letter PDFs.
    
    Args:
        name: Full name
        contact_info: Contact line
        body_paragraphs_json: JSON string of paragraph list
        target_company: Company name
        target_role: Role title
        salutation: Opening salutation
        closing: Closing phrase
        output_filename: Optional custom filename
    
    Returns:
        JSON string with result
    """
    import json
    
    try:
        body_paragraphs = json.loads(body_paragraphs_json)
        
        result = generate_cover_letter_pdf(
            name=name,
            contact_info=contact_info,
            body_paragraphs=body_paragraphs,
            target_company=target_company,
            target_role=target_role,
            salutation=salutation,
            closing=closing,
            output_filename=output_filename
        )
        return json.dumps(result)
    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON for body_paragraphs: {e}"
        })

