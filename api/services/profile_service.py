"""Profile service wrapping the existing ProfileStore with multi-user support."""

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from api.models import ProfileResponse, ProfileListItem, Skill, Experience, Preferences, Resume

# Import existing tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from job_agent_coordinator.tools.toon_format import to_toon, from_toon

logger = logging.getLogger(__name__)

# LLM config for resume parsing
OLLAMA_BASE_URL = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
PARSER_MODEL = os.getenv("OLLAMA_FAST_MODEL", "gemma3:12b")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 300))


class ProfileService:
    """
    Multi-user profile service.

    Stores profiles in user-specific directories:
    .job_cache/users/{user_id}/profiles/{profile_id}.toon
    """

    _create_lock = threading.Lock()

    def __init__(self, base_dir: Path = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".job_cache/users")
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _user_profiles_dir(self, user_id: str) -> Path:
        """Get profiles directory for a user."""
        user_dir = self.base_dir / user_id / "profiles"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    def _meta_file(self, user_id: str) -> Path:
        """Get meta file path for user."""
        return self._user_profiles_dir(user_id) / "_meta.toon"
    
    def _get_active_profile_id(self, user_id: str) -> Optional[str]:
        """Get active profile ID for user."""
        meta_file = self._meta_file(user_id)
        if meta_file.exists():
            try:
                meta = from_toon(meta_file.read_text())
                return meta.get("active_profile")
            except:
                pass
        return None
    
    def _set_active_profile_id(self, user_id: str, profile_id: str):
        """Set active profile ID for user."""
        meta_file = self._meta_file(user_id)
        meta_file.write_text(to_toon({
            "active_profile": profile_id,
            "updated_at": datetime.now().isoformat()
        }) + '\n')
    
    def _load_profile(self, user_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
        """Load a profile from disk."""
        profile_file = self._user_profiles_dir(user_id) / f"{profile_id}.toon"
        if profile_file.exists():
            try:
                return from_toon(profile_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load profile {profile_id}: {e}")
        return None
    
    def _save_profile(self, user_id: str, profile: Dict[str, Any]):
        """Save a profile to disk."""
        profile_id = profile.get("id")
        if not profile_id:
            return
        
        profile["updated_at"] = datetime.now().isoformat()
        profile_file = self._user_profiles_dir(user_id) / f"{profile_id}.toon"
        profile_file.write_text(to_toon(profile) + '\n')
    
    def _to_response(self, profile: Dict[str, Any], is_active: bool = False) -> ProfileResponse:
        """Convert profile dict to response model."""
        # Parse skills
        skills = []
        for s in profile.get("skills", []):
            added_at = s.get("added_at")
            if isinstance(added_at, str):
                added_at = datetime.fromisoformat(added_at)
            elif not isinstance(added_at, datetime):
                added_at = None

            skills.append(Skill(
                name=s.get("name", ""),
                level=s.get("level", "intermediate"),
                added_at=added_at
            ))

        # Parse experience
        experience = []
        for e in profile.get("experience", []):
            added_at = e.get("added_at")
            if isinstance(added_at, str):
                added_at = datetime.fromisoformat(added_at)
            elif not isinstance(added_at, datetime):
                added_at = None

            experience.append(Experience(
                title=e.get("title", ""),
                company=e.get("company", ""),
                start_date=e.get("start_date", ""),
                end_date=e.get("end_date", "present"),
                description=e.get("description", ""),
                added_at=added_at
            ))
        
        # Parse preferences
        prefs_data = profile.get("preferences", {})
        preferences = Preferences(
            target_roles=prefs_data.get("target_roles", []),
            target_locations=prefs_data.get("target_locations", []),
            remote_preference=prefs_data.get("remote_preference", "hybrid"),
            salary_min=prefs_data.get("salary_min"),
            salary_max=prefs_data.get("salary_max"),
            job_types=prefs_data.get("job_types", ["full-time"]),
            industries=prefs_data.get("industries", []),
            excluded_companies=prefs_data.get("excluded_companies", [])
        )
        
        # Parse resume
        resume_data = profile.get("resume", {})
        resume = Resume(
            summary=resume_data.get("summary", ""),
            content=resume_data.get("content", ""),
            last_updated=datetime.fromisoformat(resume_data["last_updated"]) if resume_data.get("last_updated") else None
        )
        
        return ProfileResponse(
            id=profile.get("id", ""),
            name=profile.get("name", ""),
            email=str(profile.get("email", "")),
            phone=str(profile.get("phone", "")),
            location=str(profile.get("location", "")),
            created_at=datetime.fromisoformat(profile.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(profile.get("updated_at", datetime.now().isoformat())),
            skills=skills,
            experience=experience,
            preferences=preferences,
            resume=resume,
            notes=profile.get("notes", ""),
            is_active=is_active
        )
    
    def list_profiles(self, user_id: str) -> List[ProfileListItem]:
        """List all profiles for a user."""
        profiles_dir = self._user_profiles_dir(user_id)
        active_id = self._get_active_profile_id(user_id)
        
        profiles = []
        for f in profiles_dir.glob("*.toon"):
            if f.name == "_meta.toon":
                continue
            try:
                data = from_toon(f.read_text())
                profiles.append(ProfileListItem(
                    id=data.get("id", f.stem),
                    name=data.get("name", "Unknown"),
                    location=data.get("location", ""),
                    skills_count=len(data.get("skills", [])),
                    is_active=data.get("id", f.stem) == active_id
                ))
            except Exception as e:
                logger.warning(f"Failed to load profile {f}: {e}")
        
        return profiles
    
    def create_profile(
        self,
        user_id: str,
        name: str,
        email: str = "",
        phone: str = "",
        location: str = "",
        skills: Optional[list] = None,
        experience: Optional[list] = None,
        preferences: Optional[dict] = None,
    ) -> Optional[ProfileResponse]:
        """Create a new profile."""
        with self._create_lock:
            # Generate ID — strip all non-alphanumeric chars except underscores/hyphens
            import re as _re
            sanitized = _re.sub(r'[^a-z0-9_-]', '', name.lower().replace(" ", "_"))[:20]
            profile_id = sanitized if sanitized else "profile"

            # Check if exists
            existing = self._load_profile(user_id, profile_id)
            if existing:
                # Append number
                i = 1
                while self._load_profile(user_id, f"{profile_id}_{i}"):
                    i += 1
                profile_id = f"{profile_id}_{i}"

            profile = {
                "id": profile_id,
                "user_id": user_id,
                "name": name,
                "email": email,
                "phone": phone,
                "location": location,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "skills": [s.dict() if hasattr(s, 'dict') else s for s in skills] if skills else [],
                "experience": [e.dict() if hasattr(e, 'dict') else e for e in experience] if experience else [],
                "education": [],
                "certifications": [],
                "preferences": (preferences.dict() if hasattr(preferences, 'dict') else preferences) if preferences else {
                    "target_roles": [],
                    "target_locations": [],
                    "remote_preference": "hybrid",
                    "salary_min": None,
                    "salary_max": None,
                    "job_types": ["full-time"],
                    "industries": [],
                    "excluded_companies": [],
                },
                "resume": {
                    "summary": "",
                    "content": "",
                    "last_updated": None,
                },
                "notes": "",
            }

            self._save_profile(user_id, profile)

            # Set as active if first profile
            if len(self.list_profiles(user_id)) == 1:
                self._set_active_profile_id(user_id, profile_id)

        logger.info(f"Created profile: {name} ({profile_id}) for user {user_id}")

        active_id = self._get_active_profile_id(user_id)
        return self._to_response(profile, is_active=profile_id == active_id)
    
    def get_profile(self, profile_id: str, user_id: str) -> Optional[ProfileResponse]:
        """Get a profile by ID."""
        profile = self._load_profile(user_id, profile_id)
        if not profile:
            return None
        
        active_id = self._get_active_profile_id(user_id)
        return self._to_response(profile, is_active=profile_id == active_id)
    
    def get_active_profile(self, user_id: str) -> Optional[ProfileResponse]:
        """Get the active profile for a user."""
        active_id = self._get_active_profile_id(user_id)
        if not active_id:
            # Return first profile if any
            profiles = self.list_profiles(user_id)
            if profiles:
                active_id = profiles[0].id
            else:
                return None
        
        return self.get_profile(active_id, user_id)
    
    def update_profile(self, profile_id: str, user_id: str, **kwargs) -> Optional[ProfileResponse]:
        """Update a profile."""
        profile = self._load_profile(user_id, profile_id)
        if not profile:
            return None
        
        # Update basic fields
        for field in ["name", "email", "phone", "location", "notes"]:
            if field in kwargs and kwargs[field] is not None:
                value = kwargs[field]
                # Strip HTML tags to prevent XSS
                if isinstance(value, str):
                    value = re.sub(r'<[^>]+>', '', value)
                profile[field] = value
        
        # Update skills
        if "skills" in kwargs and kwargs["skills"] is not None:
            profile["skills"] = [
                {
                    "name": s.get("name", "") if isinstance(s, dict) else s.name,
                    "level": s.get("level", "intermediate") if isinstance(s, dict) else (s.level.value if hasattr(s.level, 'value') else s.level),
                    "added_at": (s.get("added_at") or datetime.now().isoformat()) if isinstance(s, dict) else (s.added_at.isoformat() if s.added_at else datetime.now().isoformat())
                }
                for s in kwargs["skills"]
            ]
        
        # Update experience
        if "experience" in kwargs and kwargs["experience"] is not None:
            profile["experience"] = [
                {
                    "title": e.get("title", "") if isinstance(e, dict) else e.title,
                    "company": e.get("company", "") if isinstance(e, dict) else e.company,
                    "start_date": e.get("start_date", "") if isinstance(e, dict) else e.start_date,
                    "end_date": e.get("end_date", "present") if isinstance(e, dict) else e.end_date,
                    "description": e.get("description", "") if isinstance(e, dict) else e.description,
                    "added_at": (e.get("added_at") or datetime.now().isoformat()) if isinstance(e, dict) else (e.added_at.isoformat() if e.added_at else datetime.now().isoformat())
                }
                for e in kwargs["experience"]
            ]
        
        # Update preferences
        if "preferences" in kwargs and kwargs["preferences"] is not None:
            prefs = kwargs["preferences"]
            if isinstance(prefs, dict):
                profile["preferences"] = {
                    "target_roles": prefs.get("target_roles", []),
                    "target_locations": prefs.get("target_locations", []),
                    "remote_preference": prefs.get("remote_preference", "hybrid"),
                    "salary_min": prefs.get("salary_min"),
                    "salary_max": prefs.get("salary_max"),
                    "job_types": prefs.get("job_types", ["full-time"]),
                    "industries": prefs.get("industries", []),
                    "excluded_companies": [c.lower() for c in prefs.get("excluded_companies", [])],
                }
            else:
                profile["preferences"] = {
                    "target_roles": prefs.target_roles,
                    "target_locations": prefs.target_locations,
                    "remote_preference": prefs.remote_preference.value if hasattr(prefs.remote_preference, 'value') else prefs.remote_preference,
                    "salary_min": prefs.salary_min,
                    "salary_max": prefs.salary_max,
                    "job_types": prefs.job_types,
                    "industries": prefs.industries,
                    "excluded_companies": [c.lower() for c in prefs.excluded_companies],
                }
        
        # Update resume
        if "resume" in kwargs and kwargs["resume"] is not None:
            resume = kwargs["resume"]
            if isinstance(resume, dict):
                profile["resume"] = {
                    "summary": resume.get("summary", ""),
                    "content": resume.get("content", ""),
                    "last_updated": datetime.now().isoformat(),
                }
            else:
                profile["resume"] = {
                    "summary": resume.summary,
                    "content": resume.content,
                    "last_updated": datetime.now().isoformat(),
                }
        
        self._save_profile(user_id, profile)
        
        active_id = self._get_active_profile_id(user_id)
        return self._to_response(profile, is_active=profile_id == active_id)
    
    def delete_profile(self, profile_id: str, user_id: str) -> bool:
        """Delete a profile."""
        profile_file = self._user_profiles_dir(user_id) / f"{profile_id}.toon"
        if not profile_file.exists():
            return False
        
        profile_file.unlink()
        
        # Update active if needed
        if self._get_active_profile_id(user_id) == profile_id:
            profiles = self.list_profiles(user_id)
            if profiles:
                self._set_active_profile_id(user_id, profiles[0].id)
        
        logger.info(f"Deleted profile: {profile_id}")
        return True
    
    def set_active_profile(self, profile_id: str, user_id: str) -> Optional[ProfileResponse]:
        """Set a profile as active."""
        profile = self._load_profile(user_id, profile_id)
        if not profile:
            return None

        self._set_active_profile_id(user_id, profile_id)
        return self._to_response(profile, is_active=True)

    # ── Import Methods ──────────────────────────────────────

    def _extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes using PyMuPDF."""
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        finally:
            doc.close()

    def _parse_resume_with_llm(self, text: str) -> dict:
        """Parse resume/profile text into structured data using Ollama."""
        import requests

        prompt = f"""Parse this resume into structured JSON format. Extract ALL information you can find.

RESUME TEXT:
{text[:12000]}

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
            from job_agent_coordinator.services.llm_queue import llm_request, LLMQueue, Priority
            # Try queue first, fall back to direct call if it fails
            try:
                result = llm_request(
                    request_type="resume_parse",
                    model=PARSER_MODEL,
                    prompt=prompt,
                    options={"temperature": 0.1},
                    timeout=LLM_TIMEOUT,
                    priority=Priority.USER_INTERACTIVE,
                )
            except Exception as queue_err:
                logger.warning(f"Queue call failed ({queue_err}), calling Ollama directly")
                result = LLMQueue._call_ollama(
                    PARSER_MODEL, prompt, {"temperature": 0.1}, LLM_TIMEOUT
                )
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                return json.loads(json_match.group())
            else:
                logger.error("Could not find JSON in LLM response")
                return {}
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return {}

    def _create_profile_from_parsed(self, user_id: str, parsed: dict) -> Optional[ProfileResponse]:
        """Create a profile from LLM-parsed resume data."""
        name = parsed.get("name", "Imported Profile")
        if not name or name == "Unknown":
            name = "Imported Profile"

        # Create base profile
        profile_response = self.create_profile(
            user_id=user_id,
            name=name,
            email=parsed.get("email", ""),
            phone=parsed.get("phone", ""),
            location=parsed.get("location", ""),
        )
        if not profile_response:
            return None

        profile_id = profile_response.id

        # Build update kwargs
        update_kwargs: Dict[str, Any] = {}

        # Skills
        skills = parsed.get("skills", [])
        if skills:
            update_kwargs["skills"] = [
                {"name": s.get("name", str(s)), "level": s.get("level", "intermediate"), "added_at": datetime.now().isoformat()}
                if isinstance(s, dict) else {"name": str(s), "level": "intermediate", "added_at": datetime.now().isoformat()}
                for s in skills
                if (s.get("name") if isinstance(s, dict) else s)
            ]

        # Experience
        experience = parsed.get("experience", [])
        if experience:
            update_kwargs["experience"] = [
                {
                    "title": e.get("title", ""),
                    "company": e.get("company", ""),
                    "start_date": e.get("start_date", ""),
                    "end_date": e.get("end_date", "present"),
                    "description": e.get("description", ""),
                    "added_at": datetime.now().isoformat(),
                }
                for e in experience
                if isinstance(e, dict)
            ]

        # Preferences
        prefs = parsed.get("preferences", {})
        if prefs:
            update_kwargs["preferences"] = {
                "target_roles": prefs.get("target_roles", []),
                "target_locations": [],
                "remote_preference": prefs.get("remote_preference", "hybrid"),
                "salary_min": None,
                "salary_max": None,
                "job_types": ["full-time"],
                "industries": [],
                "excluded_companies": [],
            }

        # Resume summary
        summary = parsed.get("summary", "")
        if summary:
            update_kwargs["resume"] = {"summary": summary, "content": ""}

        # Education + certs in notes
        notes_parts = []
        for edu in parsed.get("education", []):
            if isinstance(edu, dict):
                notes_parts.append(f"Education: {edu.get('degree', '')} in {edu.get('field', '')} from {edu.get('institution', '')} ({edu.get('year', '')})")
        for cert in parsed.get("certifications", []):
            if isinstance(cert, dict):
                notes_parts.append(f"Certification: {cert.get('name', '')} ({cert.get('issuer', '')}, {cert.get('year', '')})")
        if notes_parts:
            update_kwargs["notes"] = "\n".join(notes_parts)

        if update_kwargs:
            return self.update_profile(profile_id, user_id, **update_kwargs)

        return profile_response

    def import_from_pdf(self, user_id: str, pdf_bytes: bytes) -> Optional[ProfileResponse]:
        """Import a profile from a PDF resume."""
        text = self._extract_text_from_pdf_bytes(pdf_bytes)
        if not text.strip():
            logger.error("No text found in PDF")
            return None

        logger.info(f"Extracted {len(text)} chars from PDF, parsing with LLM...")
        parsed = self._parse_resume_with_llm(text)
        if not parsed:
            logger.error("LLM failed to parse resume")
            return None

        return self._create_profile_from_parsed(user_id, parsed)

    def import_from_text(self, user_id: str, text: str) -> Optional[ProfileResponse]:
        """Import a profile from plain text resume content."""
        logger.info(f"Parsing {len(text)} chars of plain text with LLM...")
        parsed = self._parse_resume_with_llm(text)
        if not parsed:
            logger.error("LLM failed to parse resume text")
            return None

        return self._create_profile_from_parsed(user_id, parsed)

    def import_from_linkedin(self, user_id: str, linkedin_url: str) -> Optional[ProfileResponse]:
        """Import a profile from a LinkedIn profile URL."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed")
            return None

        logger.info(f"Scraping LinkedIn profile: {linkedin_url}")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()
                page.goto(linkedin_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                # Try to expand sections
                for selector in ["button:has-text('see more')", "button:has-text('Show more')"]:
                    try:
                        buttons = page.query_selector_all(selector)
                        for btn in buttons[:5]:
                            btn.click()
                            page.wait_for_timeout(500)
                    except Exception:
                        pass

                text = page.inner_text("body")
                browser.close()

        except Exception as e:
            logger.error(f"LinkedIn scrape failed: {e}")
            return None

        if not text or len(text.strip()) < 100:
            logger.error("Could not extract meaningful text from LinkedIn page")
            return None

        logger.info(f"Extracted {len(text)} chars from LinkedIn, parsing with LLM...")
        parsed = self._parse_resume_with_llm(text)
        if not parsed:
            return None

        return self._create_profile_from_parsed(user_id, parsed)
