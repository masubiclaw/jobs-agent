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


def _create_styles() -> Dict[str, ParagraphStyle]:
    """
    Create custom paragraph styles for professional, aesthetically pleasing documents.
    
    Design principles:
    - Clean, modern typography using Helvetica
    - Clear visual hierarchy with consistent spacing
    - Professional color palette (black/dark gray)
    - Balanced whitespace for elegant appearance
    """
    styles = getSampleStyleSheet()
    
    custom_styles = {
        # =========================
        # RESUME HEADER STYLES (compact for single page)
        # =========================
        "Name": ParagraphStyle(
            "Name",
            parent=styles["Heading1"],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=4,
            spaceBefore=0,
            textColor=COLOR_PRIMARY,
            fontName="Helvetica-Bold",
            leading=18,
        ),
        "ContactInfo": ParagraphStyle(
            "ContactInfo",
            parent=styles["Normal"],
            fontSize=9,
            alignment=TA_CENTER,
            spaceAfter=6,
            textColor=COLOR_SECONDARY,
            fontName="Helvetica",
            leading=12,
        ),
        
        # =========================
        # SECTION STYLES (compact)
        # =========================
        "SectionHeader": ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=10,
            spaceBefore=8,
            spaceAfter=4,
            textColor=COLOR_PRIMARY,
            fontName="Helvetica-Bold",
            leading=12,
            # Uppercase look achieved by content, not style
            letterSpacing=0.5,
        ),
        
        # =========================
        # RESUME CONTENT STYLES (compact for single page)
        # =========================
        "Summary": ParagraphStyle(
            "Summary",
            parent=styles["Normal"],
            fontSize=9,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
            leading=12,  # Tighter leading for compact layout
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "JobTitle": ParagraphStyle(
            "JobTitle",
            parent=styles["Normal"],
            fontSize=9,
            fontName="Helvetica-Bold",
            spaceAfter=1,
            spaceBefore=0,
            textColor=COLOR_PRIMARY,
            leading=11,
        ),
        "JobCompany": ParagraphStyle(
            "JobCompany",
            parent=styles["Normal"],
            fontSize=8,
            fontName="Helvetica",
            spaceAfter=3,
            textColor=COLOR_SECONDARY,
            leading=10,
        ),
        "JobDates": ParagraphStyle(
            "JobDates",
            parent=styles["Normal"],
            fontSize=8,
            fontName="Helvetica-Oblique",
            textColor=COLOR_MUTED,
            alignment=TA_RIGHT,
            leading=10,
        ),
        "JobMeta": ParagraphStyle(
            "JobMeta",
            parent=styles["Normal"],
            fontSize=8,
            textColor=COLOR_SECONDARY,
            spaceAfter=3,
            leading=10,
            fontName="Helvetica",
        ),
        "BulletPoint": ParagraphStyle(
            "BulletPoint",
            parent=styles["Normal"],
            fontSize=8,
            leftIndent=10,
            bulletIndent=0,
            spaceAfter=2,   # Compact bullet spacing
            leading=11,     # Tighter line height
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "Skills": ParagraphStyle(
            "Skills",
            parent=styles["Normal"],
            fontSize=8,
            spaceAfter=4,
            leading=11,  # Compact line height
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "Education": ParagraphStyle(
            "Education",
            parent=styles["Normal"],
            fontSize=8,
            spaceAfter=3,
            leading=11,
            textColor=COLOR_BODY,
            fontName="Helvetica",
        ),
        "EducationTitle": ParagraphStyle(
            "EducationTitle",
            parent=styles["Normal"],
            fontSize=8,
            fontName="Helvetica-Bold",
            spaceAfter=2,
            leading=10,
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
    
    return sections


def generate_resume_pdf(
    content: str,
    company: str,
    profile_name: str = "Candidate",
    output_dir: Optional[Path] = None
) -> str:
    """
    Generate an aesthetically pleasing PDF resume.
    
    Design features:
    - Clean, modern typography (Helvetica family)
    - Clear visual hierarchy with section headers and subtle rules
    - Professional color palette (black/gray tones)
    - Balanced whitespace for elegant, readable layout
    - Strictly single page
    
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
    
    # Create document with optimized margins for single page
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        leftMargin=MARGIN_SIDE,
        rightMargin=MARGIN_SIDE,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )
    
    styles = _create_styles()
    story = []
    
    # Parse content into sections
    sections = _parse_resume_sections(content)
    
    # =========================
    # HEADER: Name & Contact
    # =========================
    logger.info("  🔹 Rendering HEADER section...")
    header_lines = sections.get("header", "").split("\n")
    if header_lines:
        # First line is name - large and prominent
        name = header_lines[0].strip() if header_lines else profile_name
        logger.debug(f"    Name: {name}")
        story.append(Paragraph(name, styles["Name"]))
        
        # Contact info - elegant single line with separators
        if len(header_lines) > 1:
            contact_parts = [line.strip() for line in header_lines[1:] if line.strip()]
            contact = "  •  ".join(contact_parts)  # Use bullet separators
            logger.debug(f"    Contact: {contact[:50]}...")
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
        logger.info("  🔹 Rendering SUMMARY section...")
        story.extend(_create_section_header("Professional Summary", styles))
        summary_text = sections["summary"].replace("\n", " ").strip()
        logger.debug(f"    Summary: {summary_text[:80]}...")
        story.append(Paragraph(summary_text, styles["Summary"]))
    else:
        logger.warning("  ⚠️ No SUMMARY section found")
    
    # =========================
    # SKILLS
    # =========================
    if sections.get("skills"):
        logger.info("  🔹 Rendering SKILLS section...")
        story.extend(_create_section_header("Skills", styles))
        # Format skills with elegant separators
        skills_lines = sections["skills"].split("\n")
        skills_list = []
        for line in skills_lines:
            line = line.strip().lstrip("-•").strip()
            if line:
                skills_list.append(line)
        skills_text = "  •  ".join(skills_list) if skills_list else sections["skills"]
        logger.debug(f"    Skills count: {len(skills_list)}")
        story.append(Paragraph(skills_text, styles["Skills"]))
    else:
        logger.warning("  ⚠️ No SKILLS section found")
    
    # =========================
    # EXPERIENCE
    # =========================
    if sections.get("experience"):
        logger.info("  🔹 Rendering EXPERIENCE section...")
        story.extend(_create_section_header("Experience", styles))
        
        exp_lines = sections["experience"].split("\n")
        is_first_job = True
        job_count = 0
        bullet_count = 0
        
        def clean_markdown(text: str) -> str:
            """Remove markdown bold markers from text."""
            return text.replace("**", "").replace("*", "").strip()
        
        for line in exp_lines:
            line = line.strip()
            if not line:
                continue
            
            # Job title/company line (contains | for separation)
            if "|" in line and not line.startswith("-") and not line.startswith("•"):
                parts = [clean_markdown(p.strip()) for p in line.split("|")]
                
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
                    
                    job_count += 1
                    logger.debug(f"    Job {job_count}: {title} at {company_name}")
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
                    job_count += 1
                    logger.debug(f"    Job {job_count}: {title}")
                    story.append(Paragraph(f"<b>{title}</b>", styles["JobTitle"]))
                    story.append(Paragraph(rest, styles["JobMeta"]))
                else:
                    story.append(Paragraph(f"<b>{clean_markdown(line)}</b>", styles["JobTitle"]))
                    
            elif line.startswith("-") or line.startswith("•"):
                # Bullet points - achievements
                bullet = line.lstrip("-•").strip()
                bullet_count += 1
                story.append(Paragraph(f"•  {bullet}", styles["BulletPoint"]))
            else:
                # Fallback for non-standard formatting
                story.append(Paragraph(clean_markdown(line), styles["JobMeta"]))
        
        logger.info(f"    Rendered {job_count} jobs with {bullet_count} bullet points")
    else:
        logger.warning("  ⚠️ No EXPERIENCE section found")
    
    # =========================
    # EDUCATION
    # =========================
    if sections.get("education"):
        logger.info("  🔹 Rendering EDUCATION section...")
        story.extend(_create_section_header("Education", styles))
        is_first_edu = True
        edu_count = 0
        for line in sections["education"].split("\n"):
            line = line.strip()
            if line:
                # Add spacing between education entries
                if not is_first_edu and "|" in line:
                    story.append(Spacer(1, 4))
                is_first_edu = False
                
                # Check if it's a degree line (often contains comma or dash)
                if "|" in line:
                    parts = line.split("|")
                    degree = parts[0].strip()
                    rest = " | ".join(parts[1:]).strip()
                    edu_count += 1
                    logger.debug(f"    Education {edu_count}: {degree}")
                    story.append(Paragraph(f"<b>{degree}</b>  |  {rest}", styles["Education"]))
                else:
                    story.append(Paragraph(line, styles["Education"]))
        logger.info(f"    Rendered {edu_count} education entries")
    else:
        logger.warning("  ⚠️ No EDUCATION section found")
    
    # Build PDF
    logger.info(f"  📄 Building PDF with {len(story)} elements...")
    try:
        doc.build(story)
        
        # Validate single page
        is_single, page_count, msg = validate_single_page(str(filepath))
        if is_single:
            logger.info(f"✅ Generated resume PDF: {filepath} (1 page)")
        else:
            logger.warning(f"⚠️ Resume exceeds 1 page: {filepath} ({page_count} pages)")
        
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
    # SENDER INFO (optional header)
    # =========================
    if profile_name and profile_name != "Candidate":
        story.append(Paragraph(profile_name, styles["CLName"]))
        if contact_info:
            story.append(Paragraph(contact_info, styles["CLContact"]))
        else:
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
            opening_text.replace("\n", " ").strip(), 
            styles["BodyParagraph"]
        ))
    
    # Body paragraph 1
    if sections.get("body1"):
        story.append(Paragraph(
            sections["body1"].replace("\n", " ").strip(), 
            styles["BodyParagraph"]
        ))
    
    # Body paragraph 2
    if sections.get("body2"):
        story.append(Paragraph(
            sections["body2"].replace("\n", " ").strip(), 
            styles["BodyParagraph"]
        ))
    
    # =========================
    # CLOSING
    # =========================
    if sections.get("closing"):
        closing_text = sections["closing"].replace("\n", " ").strip()
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
    story.append(Paragraph(profile_name, styles["Signature"]))
    
    # Build PDF
    try:
        doc.build(story)
        logger.info(f"Generated cover letter PDF: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        raise
