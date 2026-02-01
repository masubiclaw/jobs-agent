"""
PDF Generator: Creates professional PDF resumes and cover letters using ReportLab.

Generates aesthetically pleasing, ATS-friendly, single-page documents with 
professional typography and modern visual design.
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, 
    Table, TableStyle, KeepTogether
)
from reportlab.lib.colors import black, HexColor, white

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

logger = logging.getLogger(__name__)

# Output directory
OUTPUT_DIR = Path("generated_documents")

# Page setup
PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN_SIDE = 0.65 * inch
MARGIN_TOP = 0.5 * inch
MARGIN_BOTTOM = 0.45 * inch

# Color palette - professional and subtle
COLOR_PRIMARY = HexColor("#1a1a1a")      # Near-black for headers
COLOR_BODY = HexColor("#2d2d2d")          # Dark gray for body text
COLOR_SECONDARY = HexColor("#555555")     # Medium gray for metadata
COLOR_ACCENT = HexColor("#666666")        # Light accent for rules
COLOR_MUTED = HexColor("#777777")         # Muted text


def _sanitize_filename(name: str) -> str:
    """Sanitize string for use in filename."""
    # Remove special characters, keep alphanumeric and spaces
    clean = re.sub(r'[^\w\s-]', '', name)
    # Replace spaces with underscores
    clean = re.sub(r'\s+', '_', clean)
    return clean[:50]  # Limit length


def _clean_markdown(text: str) -> str:
    """
    Remove markdown formatting from text for PDF rendering.
    
    Handles:
    - **bold** and __bold__
    - *italic* and _italic_
    - Combined patterns like ***bold italic***
    
    Args:
        text: Text that may contain markdown formatting
        
    Returns:
        Clean text with markdown removed
    """
    if not text:
        return ""
    
    # Remove bold markers (** and __)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)  # ***bold italic***
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)      # **bold**
    text = re.sub(r'__(.+?)__', r'\1', text)          # __bold__
    
    # Remove italic markers (* and _) - be careful with underscores in words
    text = re.sub(r'\*(.+?)\*', r'\1', text)          # *italic*
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)  # _italic_ (not mid-word)
    
    # Remove any remaining standalone markers
    text = text.replace('**', '').replace('__', '')
    
    return text.strip()


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get the number of pages in a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        Number of pages in the PDF
    
    Raises:
        RuntimeError: If PyMuPDF is not installed or file cannot be read
        FileNotFoundError: If PDF file does not exist
    """
    if not HAS_FITZ:
        raise RuntimeError("PyMuPDF (fitz) is required for page count validation. Install with: pip install PyMuPDF")
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        doc.close()
        return page_count
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
        raise RuntimeError(f"Failed to read PDF: {e}")


def validate_single_page(pdf_path: str) -> Tuple[bool, int, str]:
    """
    Validate that a PDF is exactly one page.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        Tuple of (is_single_page: bool, page_count: int, message: str)
        - is_single_page: True if exactly 1 page, False otherwise or if validation failed
        - page_count: Number of pages, or -1 if validation failed
        - message: Description of result or error
    """
    try:
        page_count = get_pdf_page_count(pdf_path)
        if page_count == 1:
            return True, page_count, "PDF is single page"
        else:
            return False, page_count, f"PDF has {page_count} pages (expected 1)"
    except (RuntimeError, FileNotFoundError) as e:
        logger.warning(f"Could not validate page count: {e}")
        return False, -1, f"Validation failed: {e}"


# Available space calculations for single-page fitting
AVAILABLE_WIDTH = PAGE_WIDTH - (2 * MARGIN_SIDE)
AVAILABLE_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

# Style adjustment levels for single-page fitting
# Each level progressively reduces font sizes and spacing to fit more content
STYLE_ADJUSTMENTS = [
    # Level 0: Default (normal) - current sizes
    {
        "name_size": 16, "contact_size": 9, "section_size": 10,
        "summary_size": 9, "job_title_size": 9, "job_meta_size": 8,
        "bullet_size": 8, "skills_size": 8, "education_size": 8,
        "leading_mult": 1.0, "spacing_mult": 1.0,
    },
    # Level 1: Slightly smaller
    {
        "name_size": 15, "contact_size": 8.5, "section_size": 9.5,
        "summary_size": 8.5, "job_title_size": 8.5, "job_meta_size": 7.5,
        "bullet_size": 7.5, "skills_size": 7.5, "education_size": 7.5,
        "leading_mult": 0.95, "spacing_mult": 0.9,
    },
    # Level 2: Compact
    {
        "name_size": 14, "contact_size": 8, "section_size": 9,
        "summary_size": 8, "job_title_size": 8, "job_meta_size": 7,
        "bullet_size": 7, "skills_size": 7, "education_size": 7,
        "leading_mult": 0.9, "spacing_mult": 0.8,
    },
    # Level 3: Very compact (minimum readable)
    {
        "name_size": 13, "contact_size": 7.5, "section_size": 8.5,
        "summary_size": 7.5, "job_title_size": 7.5, "job_meta_size": 6.5,
        "bullet_size": 6.5, "skills_size": 6.5, "education_size": 6.5,
        "leading_mult": 0.85, "spacing_mult": 0.7,
    },
]


def _calculate_story_height(story: list, available_width: float = None, available_height: float = None) -> float:
    """
    Calculate total height of all flowables in the story before rendering.
    
    Uses ReportLab's wrap() method to measure each flowable's height
    without actually rendering to PDF.
    
    Args:
        story: List of ReportLab flowables (Paragraph, Spacer, HRFlowable, etc.)
        available_width: Available width for content (defaults to AVAILABLE_WIDTH)
        available_height: Available height for content (defaults to AVAILABLE_HEIGHT)
    
    Returns:
        Total height in points that the story would occupy
    """
    if available_width is None:
        available_width = AVAILABLE_WIDTH
    if available_height is None:
        available_height = AVAILABLE_HEIGHT
    
    total_height = 0.0
    for flowable in story:
        try:
            w, h = flowable.wrap(available_width, available_height)
            total_height += h
        except Exception as e:
            # Some flowables may not support wrap() - estimate conservatively
            logger.debug(f"Could not wrap flowable {type(flowable).__name__}: {e}")
            total_height += 12  # Default estimate for one line
    
    return total_height


def _content_fits_page(story: list, margin_buffer: float = 5.0) -> Tuple[bool, float, float]:
    """
    Check if content fits on a single page with optional margin buffer.
    
    Args:
        story: List of ReportLab flowables
        margin_buffer: Extra points of margin to ensure fit (default 5pt)
    
    Returns:
        Tuple of (fits: bool, total_height: float, available_height: float)
    """
    total_height = _calculate_story_height(story)
    target_height = AVAILABLE_HEIGHT - margin_buffer
    fits = total_height <= target_height
    return fits, total_height, AVAILABLE_HEIGHT


def _trim_content_to_fit(
    sections: Dict[str, str],
    styles: Dict[str, ParagraphStyle],
    profile_name: str = "Candidate",
    margin_buffer: float = 5.0
) -> list:
    """
    Trim content from sections until the story fits on one page.
    
    Trimming strategy (in order of priority):
    1. Remove bullet points from experience (keep 2-3 per job)
    2. Shorten skills list
    3. Reduce education details
    
    Args:
        sections: Parsed resume sections (will be modified in place)
        styles: Paragraph styles to use
        profile_name: Candidate name
        margin_buffer: Extra points of margin to ensure fit
    
    Returns:
        Trimmed story list that fits on one page
    """
    max_iterations = 20  # Safety limit to prevent infinite loops
    iteration = 0
    
    # Work with a copy to preserve original
    trimmed_sections = {k: v for k, v in sections.items()}
    
    while iteration < max_iterations:
        story = _build_resume_story(trimmed_sections, styles, profile_name)
        fits, total_height, available = _content_fits_page(story, margin_buffer)
        
        if fits:
            logger.info(f"  ✂️ Content trimmed to fit after {iteration} iterations: {total_height:.0f}pt <= {available:.0f}pt")
            return story
        
        iteration += 1
        overflow = total_height - available
        logger.debug(f"  ✂️ Trim iteration {iteration}: overflow {overflow:.0f}pt")
        
        # Strategy 1: Remove bullet points from experience (from the bottom)
        if trimmed_sections.get("experience"):
            exp_lines = trimmed_sections["experience"].split("\n")
            bullet_indices = [i for i, line in enumerate(exp_lines) 
                           if line.strip().startswith("-") or line.strip().startswith("•")]
            
            if len(bullet_indices) > 6:  # Keep at least 6 bullets total
                # Remove the last bullet point
                last_bullet_idx = bullet_indices[-1]
                exp_lines.pop(last_bullet_idx)
                trimmed_sections["experience"] = "\n".join(exp_lines)
                continue
        
        # Strategy 2: Shorten skills list (remove from end)
        if trimmed_sections.get("skills"):
            skills_text = trimmed_sections["skills"]
            # Handle both comma-separated and newline-separated
            if "," in skills_text:
                skills_list = [s.strip() for s in skills_text.split(",") if s.strip()]
                if len(skills_list) > 8:  # Keep at least 8 skills
                    skills_list = skills_list[:-1]
                    trimmed_sections["skills"] = ", ".join(skills_list)
                    continue
            else:
                skills_lines = [s.strip() for s in skills_text.split("\n") if s.strip()]
                if len(skills_lines) > 4:  # Keep at least 4 skill lines
                    skills_lines = skills_lines[:-1]
                    trimmed_sections["skills"] = "\n".join(skills_lines)
                    continue
        
        # Strategy 3: Shorten summary (remove last sentence)
        if trimmed_sections.get("summary"):
            summary = trimmed_sections["summary"]
            sentences = summary.split(". ")
            if len(sentences) > 2:  # Keep at least 2 sentences
                sentences = sentences[:-1]
                trimmed_sections["summary"] = ". ".join(sentences) + "."
                continue
        
        # If we can't trim anything more, break
        logger.warning(f"  ⚠️ Cannot trim content further, still {overflow:.0f}pt overflow")
        break
    
    # Return the best we could do
    return _build_resume_story(trimmed_sections, styles, profile_name)


def _create_styles(adjustment: Optional[Dict] = None) -> Dict[str, ParagraphStyle]:
    """
    Create custom paragraph styles for professional, aesthetically pleasing documents.
    
    Design principles:
    - Clean, modern typography using Helvetica
    - Clear visual hierarchy with consistent spacing
    - Professional color palette (black/dark gray)
    - Balanced whitespace for elegant appearance
    
    Args:
        adjustment: Optional dict from STYLE_ADJUSTMENTS to scale font sizes and spacing.
                   If None, uses default (level 0) sizes.
    """
    styles = getSampleStyleSheet()
    
    # Use adjustment values or defaults
    if adjustment is None:
        adjustment = STYLE_ADJUSTMENTS[0]
    
    name_size = adjustment.get("name_size", 16)
    contact_size = adjustment.get("contact_size", 9)
    section_size = adjustment.get("section_size", 10)
    summary_size = adjustment.get("summary_size", 9)
    job_title_size = adjustment.get("job_title_size", 9)
    job_meta_size = adjustment.get("job_meta_size", 8)
    bullet_size = adjustment.get("bullet_size", 8)
    skills_size = adjustment.get("skills_size", 8)
    education_size = adjustment.get("education_size", 8)
    leading_mult = adjustment.get("leading_mult", 1.0)
    spacing_mult = adjustment.get("spacing_mult", 1.0)
    
    custom_styles = {
        # =========================
        # RESUME HEADER STYLES (compact for single page)
        # =========================
        "Name": ParagraphStyle(
            "Name",
            parent=styles["Heading1"],
            fontSize=name_size,
            alignment=TA_CENTER,
            spaceAfter=int(4 * spacing_mult),
            spaceBefore=0,
            textColor=COLOR_PRIMARY,
            fontName="Helvetica-Bold",
            leading=int(name_size * 1.125 * leading_mult),
        ),
        "ContactInfo": ParagraphStyle(
            "ContactInfo",
            parent=styles["Normal"],
            fontSize=contact_size,
            alignment=TA_CENTER,
            spaceAfter=int(6 * spacing_mult),
            textColor=COLOR_SECONDARY,
            fontName="Helvetica",
            leading=int(contact_size * 1.33 * leading_mult),
        ),
        
        # =========================
        # SECTION STYLES (compact)
        # =========================
        "SectionHeader": ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=section_size,
            spaceBefore=int(8 * spacing_mult),
            spaceAfter=int(4 * spacing_mult),
            textColor=COLOR_PRIMARY,
            fontName="Helvetica-Bold",
            leading=int(section_size * 1.2 * leading_mult),
            # Uppercase look achieved by content, not style
            letterSpacing=0.5,
        ),
        
        # =========================
        # RESUME CONTENT STYLES (compact for single page)
        # =========================
        "Summary": ParagraphStyle(
            "Summary",
            parent=styles["Normal"],
            fontSize=summary_size,
            alignment=TA_JUSTIFY,
            spaceAfter=int(6 * spacing_mult),
            leading=int(summary_size * 1.33 * leading_mult),  # Tighter leading for compact layout
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "JobTitle": ParagraphStyle(
            "JobTitle",
            parent=styles["Normal"],
            fontSize=job_title_size,
            fontName="Helvetica-Bold",
            spaceAfter=int(1 * spacing_mult),
            spaceBefore=0,
            textColor=COLOR_PRIMARY,
            leading=int(job_title_size * 1.22 * leading_mult),
        ),
        "JobCompany": ParagraphStyle(
            "JobCompany",
            parent=styles["Normal"],
            fontSize=job_meta_size,
            fontName="Helvetica",
            spaceAfter=int(3 * spacing_mult),
            textColor=COLOR_SECONDARY,
            leading=int(job_meta_size * 1.25 * leading_mult),
        ),
        "JobDates": ParagraphStyle(
            "JobDates",
            parent=styles["Normal"],
            fontSize=job_meta_size,
            fontName="Helvetica-Oblique",
            textColor=COLOR_MUTED,
            alignment=TA_RIGHT,
            leading=int(job_meta_size * 1.25 * leading_mult),
        ),
        "JobMeta": ParagraphStyle(
            "JobMeta",
            parent=styles["Normal"],
            fontSize=job_meta_size,
            textColor=COLOR_SECONDARY,
            spaceAfter=int(3 * spacing_mult),
            leading=int(job_meta_size * 1.25 * leading_mult),
            fontName="Helvetica",
        ),
        "BulletPoint": ParagraphStyle(
            "BulletPoint",
            parent=styles["Normal"],
            fontSize=bullet_size,
            leftIndent=10,
            bulletIndent=0,
            spaceAfter=int(2 * spacing_mult),   # Compact bullet spacing
            leading=int(bullet_size * 1.375 * leading_mult),     # Tighter line height
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "Skills": ParagraphStyle(
            "Skills",
            parent=styles["Normal"],
            fontSize=skills_size,
            spaceAfter=int(4 * spacing_mult),
            leading=int(skills_size * 1.375 * leading_mult),  # Compact line height
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "Education": ParagraphStyle(
            "Education",
            parent=styles["Normal"],
            fontSize=education_size,
            spaceAfter=int(3 * spacing_mult),
            leading=int(education_size * 1.375 * leading_mult),
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "EducationTitle": ParagraphStyle(
            "EducationTitle",
            parent=styles["Normal"],
            fontSize=education_size,
            fontName="Helvetica-Bold",
            spaceAfter=int(2 * spacing_mult),
            leading=int(education_size * 1.25 * leading_mult),
            textColor=COLOR_PRIMARY,
        ),
        
        # =========================
        # COVER LETTER STYLES
        # =========================
        "CLName": ParagraphStyle(
            "CLName",
            parent=styles["Normal"],
            fontSize=14,
            fontName="Helvetica-Bold",
            textColor=COLOR_PRIMARY,
            spaceAfter=2,
        ),
        "CLContact": ParagraphStyle(
            "CLContact",
            parent=styles["Normal"],
            fontSize=9,
            textColor=COLOR_SECONDARY,
            spaceAfter=16,
            leading=12,
        ),
        "Date": ParagraphStyle(
            "Date",
            parent=styles["Normal"],
            fontSize=10,
            spaceAfter=16,
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "Recipient": ParagraphStyle(
            "Recipient",
            parent=styles["Normal"],
            fontSize=10,
            spaceAfter=4,
            leading=13,
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "Salutation": ParagraphStyle(
            "Salutation",
            parent=styles["Normal"],
            fontSize=10,
            spaceAfter=12,
            spaceBefore=12,
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "BodyParagraph": ParagraphStyle(
            "BodyParagraph",
            parent=styles["Normal"],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=10,
            leading=14,
            textColor=COLOR_BODY,
            fontName="Helvetica",
            firstLineIndent=0,
        ),
        "Closing": ParagraphStyle(
            "Closing",
            parent=styles["Normal"],
            fontSize=10,
            spaceBefore=8,
            spaceAfter=24,
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "Signature": ParagraphStyle(
            "Signature",
            parent=styles["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
            textColor=COLOR_PRIMARY,
        ),
    }
    
    return custom_styles


def _create_section_header(text: str, styles: Dict[str, ParagraphStyle]) -> list:
    """Create a section header with subtle underline for visual separation."""
    return [
        Spacer(1, 6),  # Compact space before section
        Paragraph(text.upper(), styles["SectionHeader"]),
        HRFlowable(
            width="100%", 
            thickness=0.5, 
            color=COLOR_ACCENT, 
            spaceBefore=1, 
            spaceAfter=4  # Compact space after the line
        ),
    ]


def _parse_resume_sections(content: str) -> Dict[str, str]:
    """Parse resume content into sections.
    
    Handles multiple formats:
    - Bracketed: [SUMMARY], [SKILLS], etc.
    - Plain: SUMMARY, SKILLS, etc.
    - Markdown bold: **SUMMARY**, **SKILLS**, etc.
    """
    logger.info("📄 Parsing resume content into sections...")
    logger.debug(f"Content length: {len(content)} chars, {len(content.split(chr(10)))} lines")
    
    sections = {
        "header": "",
        "summary": "",
        "skills": "",
        "experience": "",
        "education": "",
        "publications": "",
    }
    
    def is_section_header(line: str, *keywords) -> bool:
        """Check if line matches any of the section keywords."""
        line_clean = line.strip().upper()
        # Remove markdown bold markers
        line_clean = line_clean.replace("**", "").replace("*", "")
        # Remove brackets
        line_clean = line_clean.replace("[", "").replace("]", "")
        line_clean = line_clean.strip()
        
        for keyword in keywords:
            if line_clean == keyword or line_clean == keyword + ":":
                return True
        return False
    
    # Split by section markers
    lines = content.split("\n")
    current_section = "header"
    current_content = []
    
    for line in lines:
        # Check for section headers
        if is_section_header(line, "HEADER"):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            logger.debug(f"  Found HEADER section marker")
            current_section = "header"
            current_content = []
        elif is_section_header(line, "SUMMARY", "PROFESSIONAL SUMMARY"):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            logger.debug(f"  Found SUMMARY section marker")
            current_section = "summary"
            current_content = []
        elif is_section_header(line, "SKILLS", "TECHNICAL SKILLS", "CORE SKILLS"):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            logger.debug(f"  Found SKILLS section marker")
            current_section = "skills"
            current_content = []
        elif is_section_header(line, "EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE"):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            logger.debug(f"  Found EXPERIENCE section marker")
            current_section = "experience"
            current_content = []
        elif is_section_header(line, "EDUCATION"):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            logger.debug(f"  Found EDUCATION section marker")
            current_section = "education"
            current_content = []
        elif is_section_header(line, "PUBLICATIONS"):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            logger.debug(f"  Found PUBLICATIONS section marker")
            current_section = "publications"
            current_content = []
        else:
            if line.strip():
                current_content.append(line)
    
    # Don't forget the last section
    if current_content:
        sections[current_section] = "\n".join(current_content)
    
    # Log parsing summary
    for section_name, section_content in sections.items():
        line_count = len(section_content.split("\n")) if section_content else 0
        char_count = len(section_content)
        status = "✓" if section_content else "✗"
        logger.info(f"  {status} {section_name.upper()}: {line_count} lines, {char_count} chars")
    
    return sections


def _parse_cover_letter_sections(content: str) -> Dict[str, str]:
    """Parse cover letter content into sections."""
    sections = {
        "date": datetime.now().strftime("%B %d, %Y"),
        "recipient": "",
        "opening": "",
        "body1": "",
        "body2": "",
        "closing": "",
        "signature": "",
    }
    
    lines = content.split("\n")
    current_section = "date"
    current_content = []
    
    for line in lines:
        line_upper = line.strip().upper()
        
        if "[DATE]" in line_upper:
            current_section = "date"
            current_content = []
        elif "[RECIPIENT]" in line_upper:
            if current_content:
                sections["date"] = "\n".join(current_content) or sections["date"]
            current_section = "recipient"
            current_content = []
        elif "[OPENING]" in line_upper:
            if current_content:
                sections[current_section] = "\n".join(current_content)
            current_section = "opening"
            current_content = []
        elif "[BODY PARAGRAPH 1]" in line_upper or "[BODY1]" in line_upper:
            if current_content:
                sections[current_section] = "\n".join(current_content)
            current_section = "body1"
            current_content = []
        elif "[BODY PARAGRAPH 2]" in line_upper or "[BODY2]" in line_upper:
            if current_content:
                sections[current_section] = "\n".join(current_content)
            current_section = "body2"
            current_content = []
        elif "[CLOSING]" in line_upper:
            if current_content:
                sections[current_section] = "\n".join(current_content)
            current_section = "closing"
            current_content = []
        else:
            if line.strip():
                current_content.append(line)
    
    if current_content:
        sections[current_section] = "\n".join(current_content)
    
    # Post-process: Remove name/signature from closing paragraph
    # The LLM often appends the name at the end - we add it separately
    if sections.get("closing"):
        closing_lines = sections["closing"].split("\n")
        cleaned_closing = []
        for line in closing_lines:
            line_stripped = line.strip()
            # Skip lines that look like a signature (short, name-like, no punctuation at end)
            # Typical patterns: "Justin Masui", "John Doe", "Sincerely,\nName"
            if line_stripped:
                # Skip if it's just 1-3 words and no sentence punctuation
                words = line_stripped.split()
                is_signature_line = (
                    len(words) <= 3 and 
                    not line_stripped.endswith(('.', '!', '?')) and
                    not line_stripped.lower().startswith(('i ', 'my ', 'the ', 'thank', 'please'))
                )
                # Also skip common closing phrases that should be separate
                is_closing_phrase = line_stripped.lower().rstrip(',') in [
                    'sincerely', 'best regards', 'regards', 'best', 'warm regards',
                    'kind regards', 'respectfully', 'yours truly', 'thank you'
                ]
                if not is_signature_line or is_closing_phrase:
                    cleaned_closing.append(line)
        
        sections["closing"] = "\n".join(cleaned_closing)
    
    return sections


def _build_resume_story(sections: Dict[str, str], styles: Dict[str, ParagraphStyle], profile_name: str = "Candidate") -> list:
    """
    Build the story (list of flowables) for a resume PDF.
    
    Separated from generate_resume_pdf to allow pre-calculation of height
    before actual PDF generation.
    
    Args:
        sections: Parsed resume sections from _parse_resume_sections()
        styles: Paragraph styles from _create_styles()
        profile_name: Candidate name (fallback if not in sections)
    
    Returns:
        List of ReportLab flowables
    """
    story = []
    
    # =========================
    # HEADER: Name & Contact
    # =========================
    header_lines = sections.get("header", "").split("\n")
    if header_lines:
        # First line is name - large and prominent (clean markdown like **Name**)
        name = _clean_markdown(header_lines[0]) if header_lines else profile_name
        story.append(Paragraph(name, styles["Name"]))
        
        # Contact info - elegant single line with separators
        if len(header_lines) > 1:
            contact_parts = [_clean_markdown(line) for line in header_lines[1:] if line.strip()]
            contact = "  •  ".join(contact_parts)  # Use bullet separators
            story.append(Paragraph(contact, styles["ContactInfo"]))
    
    # Elegant separator line
    story.append(Spacer(1, 2))
    story.append(HRFlowable(
        width="100%", 
        thickness=1, 
        color=COLOR_PRIMARY,
        spaceBefore=0,
        spaceAfter=4
    ))
    
    # =========================
    # PROFESSIONAL SUMMARY
    # =========================
    if sections.get("summary"):
        story.extend(_create_section_header("Professional Summary", styles))
        summary_text = _clean_markdown(sections["summary"].replace("\n", " "))
        story.append(Paragraph(summary_text, styles["Summary"]))
    
    # =========================
    # SKILLS
    # =========================
    if sections.get("skills"):
        story.extend(_create_section_header("Skills", styles))
        # Format skills with elegant separators
        skills_lines = sections["skills"].split("\n")
        skills_list = []
        for line in skills_lines:
            line = _clean_markdown(line.strip().lstrip("-•"))
            if line:
                skills_list.append(line)
        skills_text = "  •  ".join(skills_list) if skills_list else _clean_markdown(sections["skills"])
        story.append(Paragraph(skills_text, styles["Skills"]))
    
    # =========================
    # EXPERIENCE
    # =========================
    if sections.get("experience"):
        story.extend(_create_section_header("Experience", styles))
        
        exp_lines = sections["experience"].split("\n")
        is_first_job = True
        
        for line in exp_lines:
            line = line.strip()
            if not line:
                continue
            
            # Job title/company line (contains | for separation)
            if "|" in line and not line.startswith("-") and not line.startswith("•"):
                parts = [_clean_markdown(p.strip()) for p in line.split("|")]
                
                if len(parts) >= 3:
                    # Format: Title | Company | Dates
                    title = parts[0]
                    company_name = parts[1]
                    dates = parts[2] if len(parts) > 2 else ""
                    
                    # Add spacing between jobs (compact for single page)
                    if is_first_job:
                        is_first_job = False
                    else:
                        story.append(Spacer(1, 6))  # Compact visual separation between jobs
                    
                    story.append(Paragraph(f"<b>{title}</b>", styles["JobTitle"]))
                    if dates:
                        story.append(Paragraph(
                            f"{company_name}  |  <i>{dates}</i>", 
                            styles["JobMeta"]
                        ))
                    else:
                        story.append(Paragraph(company_name, styles["JobCompany"]))
                elif len(parts) == 2:
                    title = parts[0]
                    rest = parts[1]
                    if is_first_job:
                        is_first_job = False
                    else:
                        story.append(Spacer(1, 6))
                    story.append(Paragraph(f"<b>{title}</b>", styles["JobTitle"]))
                    story.append(Paragraph(rest, styles["JobMeta"]))
                else:
                    story.append(Paragraph(f"<b>{_clean_markdown(line)}</b>", styles["JobTitle"]))
                    
            elif line.startswith("-") or line.startswith("•"):
                # Bullet points - achievements (already formatted)
                bullet = _clean_markdown(line.lstrip("-•").strip())
                if bullet:
                    story.append(Paragraph(f"•  {bullet}", styles["BulletPoint"]))
            else:
                # Treat any other experience content as a bullet point
                # (LLM may not have properly prefixed it)
                clean_line = _clean_markdown(line.strip())
                if clean_line:
                    story.append(Paragraph(f"•  {clean_line}", styles["BulletPoint"]))
    
    # =========================
    # EDUCATION
    # =========================
    if sections.get("education"):
        story.extend(_create_section_header("Education", styles))
        is_first_edu = True
        for line in sections["education"].split("\n"):
            line = _clean_markdown(line)
            if line:
                # Add spacing between education entries
                if not is_first_edu and "|" in line:
                    story.append(Spacer(1, 4))
                is_first_edu = False
                
                # Check if it's a degree line (often contains comma or dash)
                if "|" in line:
                    parts = line.split("|")
                    degree = _clean_markdown(parts[0])
                    rest = " | ".join([_clean_markdown(p) for p in parts[1:]])
                    story.append(Paragraph(f"<b>{degree}</b>  |  {rest}", styles["Education"]))
                else:
                    story.append(Paragraph(line, styles["Education"]))
    
    # =========================
    # PUBLICATIONS
    # =========================
    if sections.get("publications"):
        story.extend(_create_section_header("Publications", styles))
        for line in sections["publications"].split("\n"):
            line = _clean_markdown(line)
            if line:
                # Format: "Title" - Venue, Year or just Title - Venue (Year)
                if " - " in line:
                    parts = line.split(" - ", 1)
                    title = _clean_markdown(parts[0])
                    venue = _clean_markdown(parts[1]) if len(parts) > 1 else ""
                    story.append(Paragraph(f"<b>{title}</b> - {venue}", styles["Education"]))
                else:
                    story.append(Paragraph(line, styles["Education"]))
    
    return story


def generate_resume_pdf(
    content: str,
    company: str,
    profile_name: str = "Candidate",
    output_dir: Optional[Path] = None
) -> str:
    """
    Generate an aesthetically pleasing PDF resume with automatic single-page fitting.
    
    Design features:
    - Clean, modern typography (Helvetica family)
    - Clear visual hierarchy with section headers and subtle rules
    - Professional color palette (black/gray tones)
    - Balanced whitespace for elegant, readable layout
    - Automatic style adjustment to ensure single-page fit
    
    The function iteratively tries smaller font sizes and tighter spacing
    until content fits on exactly one page. If style adjustments aren't enough,
    content is trimmed as a last resort.
    
    Args:
        content: Resume content (from document generator)
        company: Company name for filename
        profile_name: Candidate name
        output_dir: Output directory (default: generated_documents/)
    
    Returns:
        Path to generated PDF file
    """
    logger.info(f"📝 Generating resume PDF for {company}")
    
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)
    
    # Generate filename
    date_str = datetime.now().strftime("%Y-%m-%d")
    company_clean = _sanitize_filename(company)
    filename = f"{company_clean}_{date_str}_resume.pdf"
    filepath = output_dir / filename
    logger.info(f"  Output file: {filepath}")
    
    # Parse content into sections (do this once)
    sections = _parse_resume_sections(content)
    
    # Try each style adjustment level until content fits
    selected_level = 0
    selected_styles = None
    selected_story = None
    
    for level, adjustment in enumerate(STYLE_ADJUSTMENTS):
        styles = _create_styles(adjustment)
        story = _build_resume_story(sections, styles, profile_name)
        
        # Calculate height before building
        fits, total_height, available = _content_fits_page(story)
        
        if fits:
            logger.info(f"  ✅ Content fits at style level {level}: {total_height:.0f}pt <= {available:.0f}pt")
            selected_level = level
            selected_styles = styles
            selected_story = story
            break
        else:
            overflow = total_height - available
            logger.info(f"  📏 Level {level}: {total_height:.0f}pt > {available:.0f}pt (overflow: {overflow:.0f}pt), trying smaller styles...")
    else:
        # None of the style levels fit - try content trimming with smallest styles
        logger.info(f"  ✂️ Style adjustments insufficient, attempting content trimming...")
        selected_level = len(STYLE_ADJUSTMENTS) - 1
        selected_styles = _create_styles(STYLE_ADJUSTMENTS[-1])
        selected_story = _trim_content_to_fit(sections, selected_styles, profile_name)
        
        # Check if trimming worked
        fits, total_height, available = _content_fits_page(selected_story)
        if fits:
            logger.info(f"  ✅ Content fits after trimming: {total_height:.0f}pt <= {available:.0f}pt")
        else:
            logger.warning(f"  ⚠️ Content still doesn't fit after trimming: {total_height:.0f}pt > {available:.0f}pt")
    
    # Create document with optimized margins for single page
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        leftMargin=MARGIN_SIDE,
        rightMargin=MARGIN_SIDE,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )
    
    # Build PDF
    logger.info(f"  📄 Building PDF with {len(selected_story)} elements at style level {selected_level}...")
    try:
        doc.build(selected_story)
        
        # Validate single page
        is_single, page_count, msg = validate_single_page(str(filepath))
        if is_single:
            logger.info(f"✅ Generated resume PDF: {filepath} (1 page, style level {selected_level})")
        else:
            logger.warning(f"⚠️ Resume exceeds 1 page: {filepath} ({page_count} pages) - content trimming may be needed")
        
        return str(filepath)
    except Exception as e:
        logger.error(f"❌ Failed to generate PDF: {e}")
        raise


def generate_cover_letter_pdf(
    content: str,
    company: str,
    profile_name: str = "Candidate",
    contact_info: str = "",
    output_dir: Optional[Path] = None
) -> str:
    """
    Generate an aesthetically pleasing PDF cover letter.
    
    Design features:
    - Professional business letter format
    - Matching typography to resume for cohesive package
    - Generous margins for elegant appearance
    - Clean, readable body text
    - Proper spacing between sections
    
    Args:
        content: Cover letter content (from document generator)
        company: Company name for filename
        profile_name: Candidate name
        contact_info: Optional contact info for header
        output_dir: Output directory (default: generated_documents/)
    
    Returns:
        Path to generated PDF file
    """
    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)
    
    # Generate filename
    date_str = datetime.now().strftime("%Y-%m-%d")
    company_clean = _sanitize_filename(company)
    filename = f"{company_clean}_{date_str}_coverletter.pdf"
    filepath = output_dir / filename
    
    # Create document with generous margins for elegant appearance
    margin_cover = 0.85 * inch
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        leftMargin=margin_cover,
        rightMargin=margin_cover,
        topMargin=margin_cover * 0.8,
        bottomMargin=margin_cover * 0.7,
    )
    
    styles = _create_styles()
    story = []
    
    # Parse content
    sections = _parse_cover_letter_sections(content)
    
    # =========================
    # SENDER INFO (header with name and contact)
    # =========================
    if profile_name and profile_name != "Candidate":
        story.append(Paragraph(_clean_markdown(profile_name), styles["CLName"]))
    if contact_info:
        # Contact info prominently displayed below name
        story.append(Paragraph(_clean_markdown(contact_info), styles["CLContact"]))
    elif profile_name and profile_name != "Candidate":
        story.append(Spacer(1, 8))
    
    # =========================
    # DATE
    # =========================
    date_text = sections.get("date") or datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(date_text, styles["Date"]))
    
    # =========================
    # RECIPIENT
    # =========================
    if sections.get("recipient"):
        recipient_lines = sections["recipient"].split("\n")
        for line in recipient_lines:
            if line.strip():
                story.append(Paragraph(line.strip(), styles["Recipient"]))
        story.append(Spacer(1, 8))
    
    # =========================
    # SALUTATION
    # =========================
    # Look for salutation in opening, or add default
    opening_text = sections.get("opening", "")
    if opening_text.startswith("Dear"):
        # First line is salutation
        opening_lines = opening_text.split("\n", 1)
        salutation = opening_lines[0]
        opening_text = opening_lines[1] if len(opening_lines) > 1 else ""
        story.append(Paragraph(salutation, styles["Salutation"]))
    else:
        story.append(Paragraph("Dear Hiring Manager,", styles["Salutation"]))
    
    # =========================
    # BODY PARAGRAPHS
    # =========================
    # Opening paragraph
    if opening_text:
        story.append(Paragraph(
            _clean_markdown(opening_text.replace("\n", " ")), 
            styles["BodyParagraph"]
        ))
    
    # Body paragraph 1
    if sections.get("body1"):
        story.append(Paragraph(
            _clean_markdown(sections["body1"].replace("\n", " ")), 
            styles["BodyParagraph"]
        ))
    
    # Body paragraph 2
    if sections.get("body2"):
        story.append(Paragraph(
            _clean_markdown(sections["body2"].replace("\n", " ")), 
            styles["BodyParagraph"]
        ))
    
    # =========================
    # CLOSING
    # =========================
    if sections.get("closing"):
        closing_text = _clean_markdown(sections["closing"].replace("\n", " "))
        # Check if closing includes "Sincerely" or similar
        if not any(word in closing_text.lower() for word in ["sincerely", "regards", "best"]):
            story.append(Paragraph(closing_text, styles["BodyParagraph"]))
            story.append(Paragraph("Sincerely,", styles["Closing"]))
        else:
            # Extract the closing salutation if present
            story.append(Paragraph(closing_text, styles["BodyParagraph"]))
    else:
        story.append(Paragraph("Sincerely,", styles["Closing"]))
    
    # =========================
    # SIGNATURE
    # =========================
    story.append(Spacer(1, 18))
    story.append(Paragraph(_clean_markdown(profile_name), styles["Signature"]))
    
    # Build PDF
    try:
        doc.build(story)
        logger.info(f"Generated cover letter PDF: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        raise
