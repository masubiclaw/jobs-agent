#!/usr/bin/env python3
"""
Import a user profile from a PDF resume using LLM parsing.

Extracts:
- Personal info (name, email, phone, location)
- Skills and proficiency levels
- Work experience
- Education
- Certifications
- Professional summary

Usage:
    python scripts/import_profile_from_pdf.py /path/to/resume.pdf
    python scripts/import_profile_from_pdf.py resume.pdf --profile-id my_profile
    python scripts/import_profile_from_pdf.py resume.pdf --dry-run  # Preview only
"""

import argparse
import json
import logging
import re
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load .env
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    logger.info("Read env file")
    load_dotenv(_env_file)

parser_model = os.getenv("OLLAMA_FAST_MODEL", "gemma3:12b")

# Try to import PDF library
try:
    import fitz  # PyMuPDF
    PDF_LIB = "pymupdf"
except ImportError:
    try:
        import pdfplumber
        PDF_LIB = "pdfplumber"
    except ImportError:
        PDF_LIB = None


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text content from PDF file."""
    if PDF_LIB == "pymupdf":
        import fitz
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    elif PDF_LIB == "pdfplumber":
        import pdfplumber
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    else:
        raise ImportError(
            "No PDF library found. Install one of:\n"
            "  pip install PyMuPDF\n"
            "  pip install pdfplumber"
        )


def parse_resume_with_llm(resume_text: str, model: str = parser_model) -> dict:
    """Use Ollama to parse resume text into structured data."""
    import requests, os
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 120))
    
    prompt = f"""Parse this resume into structured JSON format. Extract ALL information you can find.

RESUME TEXT:
{resume_text[:12000]}

OUTPUT FORMAT (JSON only, no other text):
{{
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "phone number or empty string",
    "location": "City, State/Country",
    "summary": "2-3 sentence professional summary",
    "skills": [
        {{"name": "Skill Name", "level": "expert|advanced|intermediate|beginner"}}
    ],
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "start_date": "YYYY-MM or just YYYY",
            "end_date": "YYYY-MM or present",
            "description": "Brief description of role and achievements"
        }}
    ],
    "education": [
        {{
            "degree": "Degree Type",
            "field": "Field of Study",
            "institution": "School Name",
            "year": "Graduation Year"
        }}
    ],
    "certifications": [
        {{"name": "Certification Name", "issuer": "Issuing Org", "year": "Year or empty"}}
    ],
    "preferences": {{
        "target_roles": ["list of job titles this person would be good for"],
        "remote_preference": "remote|hybrid|onsite (infer from resume if possible)"
    }}
}}

IMPORTANT:
- For skills, infer proficiency based on context (years of experience, certifications, etc.)
- Extract ALL skills mentioned, including tools, languages, frameworks
- For target_roles, suggest 3-5 roles this person is qualified for
- Output ONLY valid JSON, no explanations"""

    try:
        base_url = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
        url = base_url.rstrip("/") + "/api/generate"
        response = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            },
            timeout=LLM_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json().get("response", "")
        
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            return json.loads(json_match.group())
        else:
            logger.error("Could not find JSON in LLM response")
            logger.debug(f"Response: {result[:500]}")
            return {}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to Ollama: {e}")
        logger.info("Make sure Ollama is running: ollama serve")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        return {}


def create_profile_from_parsed(parsed: dict, profile_id: str = None) -> dict:
    """Create a profile from parsed resume data."""
    from job_agent_coordinator.tools.profile_store import get_store
    from datetime import datetime
    
    store = get_store()
    
    name = parsed.get("name", "Unknown")
    email = parsed.get("email", "")
    phone = parsed.get("phone", "")
    location = parsed.get("location", "")
    
    # Generate profile ID if not provided
    if not profile_id:
        profile_id = name.lower().replace(" ", "_").replace(".", "")[:20]
    
    # Create or update profile
    profile = store.create(
        name=name,
        email=email,
        phone=phone,
        location=location,
        profile_id=profile_id
    )
    
    # Add skills
    for skill in parsed.get("skills", []):
        if isinstance(skill, dict):
            skill_name = skill.get("name", "")
            level = skill.get("level", "intermediate")
        else:
            skill_name = str(skill).strip()
            level = "intermediate"
        if skill_name:
            store.add_skill(skill_name, level, profile_id)
    
    # Add experience
    for exp in parsed.get("experience", []):
        store.add_experience(
            title=exp.get("title", ""),
            company=exp.get("company", ""),
            start_date=exp.get("start_date", ""),
            end_date=exp.get("end_date", "present"),
            description=exp.get("description", ""),
            profile_id=profile_id
        )
    
    # Add education (store in notes for now since no dedicated method)
    edu_lines = []
    for edu in parsed.get("education", []):
        edu_lines.append(f"- {edu.get('degree', '')} in {edu.get('field', '')} from {edu.get('institution', '')} ({edu.get('year', '')})")
    
    # Add certifications to notes
    cert_lines = []
    for cert in parsed.get("certifications", []):
        cert_lines.append(f"- {cert.get('name', '')} ({cert.get('issuer', '')}, {cert.get('year', '')})")
    
    # Update notes with education and certs
    notes_parts = []
    if edu_lines:
        notes_parts.append("EDUCATION:\n" + "\n".join(edu_lines))
    if cert_lines:
        notes_parts.append("CERTIFICATIONS:\n" + "\n".join(cert_lines))
    
    if notes_parts:
        store.update(profile_id, notes="\n\n".join(notes_parts))
    
    # Set resume summary
    summary = parsed.get("summary", "")
    if summary:
        store.set_resume(summary=summary, profile_id=profile_id)
    
    # Set preferences
    prefs = parsed.get("preferences", {})
    if prefs:
        target_roles = prefs.get("target_roles", [])
        remote_pref = prefs.get("remote_preference", "hybrid")
        store.set_preferences(
            target_roles=target_roles,
            remote_preference=remote_pref,
            profile_id=profile_id
        )
    
    return store.get(profile_id)


def format_preview(parsed: dict) -> str:
    """Format parsed data for preview."""
    lines = [
        "=" * 70,
        "PARSED RESUME PREVIEW",
        "=" * 70,
        "",
        f"[personal_info]",
        f"  name: {parsed.get('name', 'N/A')}",
        f"  email: {parsed.get('email', 'N/A')}",
        f"  phone: {parsed.get('phone', 'N/A')}",
        f"  location: {parsed.get('location', 'N/A')}",
        "",
        f"[summary]",
        f"  {parsed.get('summary', 'N/A')[:200]}",
        "",
        f"[skills] ({len(parsed.get('skills', []))} found)",
    ]
    
    for skill in parsed.get("skills", [])[:15]:
        if isinstance(skill, dict):
            lines.append(f"  - {skill.get('name', '?')}: {skill.get('level', '?')}")
        else:
            lines.append(f"  - {skill}")
    if len(parsed.get("skills", [])) > 15:
        lines.append(f"  ... and {len(parsed['skills']) - 15} more")
    
    lines.extend([
        "",
        f"[experience] ({len(parsed.get('experience', []))} found)",
    ])
    for exp in parsed.get("experience", [])[:5]:
        lines.append(f"  - {exp.get('title', '?')} @ {exp.get('company', '?')} ({exp.get('start_date', '?')} - {exp.get('end_date', '?')})")
    
    lines.extend([
        "",
        f"[education] ({len(parsed.get('education', []))} found)",
    ])
    for edu in parsed.get("education", [])[:3]:
        lines.append(f"  - {edu.get('degree', '?')} in {edu.get('field', '?')} from {edu.get('institution', '?')}")
    
    lines.extend([
        "",
        f"[certifications] ({len(parsed.get('certifications', []))} found)",
    ])
    for cert in parsed.get("certifications", [])[:5]:
        lines.append(f"  - {cert.get('name', '?')}")
    
    prefs = parsed.get("preferences", {})
    if prefs.get("target_roles"):
        lines.extend([
            "",
            f"[suggested_roles]",
            f"  {', '.join(prefs['target_roles'][:5])}",
        ])
    
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Import profile from PDF resume using LLM parsing"
    )
    parser.add_argument("pdf_path", help="Path to PDF resume file")
    parser.add_argument("--profile-id", help="Custom profile ID (default: generated from name)")
    parser.add_argument("--model", default="gemma3:12b", help="Ollama model to use (default: gemma3:12b)")
    parser.add_argument("--dry-run", action="store_true", help="Preview parsed data without saving")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)
    
    if not pdf_path.suffix.lower() == ".pdf":
        print(f"❌ Not a PDF file: {pdf_path}")
        sys.exit(1)
    
    print(f"📄 Reading PDF: {pdf_path}")
    
    # Extract text
    try:
        text = extract_text_from_pdf(pdf_path)
        print(f"   Extracted {len(text):,} characters")
    except ImportError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to read PDF: {e}")
        sys.exit(1)
    
    if not text.strip():
        print("❌ No text found in PDF (might be scanned/image-based)")
        sys.exit(1)
    
    # Parse with LLM
    print(f"🤖 Parsing with {args.model}...")
    parsed = parse_resume_with_llm(text, model=args.model)
    
    if not parsed:
        print("❌ Failed to parse resume")
        sys.exit(1)
    
    # Show preview
    print(format_preview(parsed))
    
    if args.dry_run:
        print("🔍 DRY RUN - No changes saved")
        return
    
    # Create profile
    print("\n💾 Saving profile...")
    profile = create_profile_from_parsed(parsed, args.profile_id)
    
    print(f"""
✅ Profile created successfully!

[profile]
  id: {profile.get('id')}
  name: {profile.get('name')}
  location: {profile.get('location')}
  skills: {len(profile.get('skills', []))}
  experience: {len(profile.get('experience', []))}

📍 Stored at: .job_cache/profiles/{profile.get('id')}.toon

Next steps:
  - View profile: python -c "from job_agent_coordinator.tools.profile_store import get_store; print(get_store().get('{profile.get('id')}'))"
  - Set as active: The profile is already active
  - Run job matching: python scripts/run_job_matcher.py --limit 50
""")


if __name__ == "__main__":
    main()
