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
        """Load a profile from disk (JSON preferred, TOON fallback with migration)."""
        profiles_dir = self._user_profiles_dir(user_id)
        json_file = profiles_dir / f"{profile_id}.json"
        toon_file = profiles_dir / f"{profile_id}.toon"

        # Prefer JSON (reliable for nested data)
        if json_file.exists():
            try:
                return json.loads(json_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load profile JSON {profile_id}: {e}")

        # Fallback: TOON (migrate to JSON)
        if toon_file.exists():
            try:
                data = from_toon(toon_file.read_text())
                if data and isinstance(data, dict):
                    # Check if nested data was parsed properly
                    if data.get("skills") and isinstance(data["skills"], list) and len(data["skills"]) > 0:
                        # TOON parsed OK — save as JSON and return
                        json_file.write_text(json.dumps(data, indent=2, default=str))
                        logger.info(f"Migrated profile {profile_id} from TOON to JSON")
                        return data
                    else:
                        # TOON parser failed on nested data — parse manually
                        data = self._parse_profile_toon(toon_file.read_text())
                        if data:
                            json_file.write_text(json.dumps(data, indent=2, default=str))
                            logger.info(f"Migrated profile {profile_id} from TOON (manual parse) to JSON")
                            return data
            except Exception as e:
                logger.error(f"Failed to load profile TOON {profile_id}: {e}")
        return None

    @staticmethod
    def _parse_profile_toon(text: str) -> Optional[Dict[str, Any]]:
        """Manually parse a profile TOON file with nested arrays."""
        import re
        profile: Dict[str, Any] = {}
        current_section = None
        current_item: Optional[Dict[str, Any]] = None
        current_list: Optional[list] = None

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # Top-level section: [skills], [experience], [preferences], etc.
            section_match = re.match(r'^\[(\w+)\]$', stripped)
            if section_match:
                name = section_match.group(1)
                if name.isdigit():
                    # Array item index [0], [1], etc.
                    if current_item and current_list is not None:
                        current_list.append(current_item)
                    current_item = {}
                else:
                    # Save previous list
                    if current_item and current_list is not None:
                        current_list.append(current_item)
                        current_item = None
                    if current_section and current_list is not None:
                        profile[current_section] = current_list

                    current_section = name
                    if name in ('skills', 'experience', 'education', 'certifications'):
                        current_list = []
                        current_item = None
                    else:
                        current_list = None
                        current_item = None
                        if name not in profile:
                            profile[name] = {}
                continue

            # Key-value pair
            if ':' in stripped:
                key, _, value = stripped.partition(':')
                key = key.strip()
                value = value.strip()

                # Convert types
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                elif value.lower() in ('none', 'null', ''):
                    value = None

                if current_item is not None:
                    current_item[key] = value
                elif current_section and isinstance(profile.get(current_section), dict):
                    profile[current_section][key] = value
                else:
                    profile[key] = value

        # Flush last item/section
        if current_item and current_list is not None:
            current_list.append(current_item)
        if current_section and current_list is not None:
            profile[current_section] = current_list

        return profile if profile.get('id') else None

    def _save_profile(self, user_id: str, profile: Dict[str, Any]):
        """Save a profile to disk as JSON."""
        profile_id = profile.get("id")
        if not profile_id:
            return

        profile["updated_at"] = datetime.now().isoformat()
        profiles_dir = self._user_profiles_dir(user_id)
        json_file = profiles_dir / f"{profile_id}.json"
        json_file.write_text(json.dumps(profile, indent=2, default=str))
    
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
                name=str(s.get("name", "") or ""),
                level=str(s.get("level", "intermediate") or "intermediate"),
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
                title=str(e.get("title", "") or ""),
                company=str(e.get("company", "") or ""),
                start_date=str(e.get("start_date", "") or ""),
                end_date=str(e.get("end_date", "present") or "present"),
                description=str(e.get("description", "") or ""),
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
        """List all profiles for a user (JSON preferred, TOON fallback)."""
        profiles_dir = self._user_profiles_dir(user_id)
        active_id = self._get_active_profile_id(user_id)
        seen_ids = set()

        profiles = []
        # Load JSON profiles first
        for f in profiles_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                pid = data.get("id", f.stem)
                seen_ids.add(pid)
                profiles.append(ProfileListItem(
                    id=pid,
                    name=data.get("name", "Unknown"),
                    location=data.get("location", ""),
                    skills_count=len(data.get("skills", [])),
                    is_active=pid == active_id
                ))
            except Exception as e:
                logger.warning(f"Failed to load profile {f}: {e}")

        # Then TOON profiles not already loaded as JSON
        for f in profiles_dir.glob("*.toon"):
            if f.name == "_meta.toon":
                continue
            if f.stem in seen_ids:
                continue
            try:
                # Try loading via _load_profile which handles migration
                data = self._load_profile(user_id, f.stem)
                if data:
                    pid = data.get("id", f.stem)
                    seen_ids.add(pid)
                    profiles.append(ProfileListItem(
                        id=pid,
                        name=data.get("name", "Unknown"),
                        location=data.get("location", ""),
                        skills_count=len(data.get("skills", [])),
                        is_active=pid == active_id
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
        """Delete a profile (handles both JSON and TOON formats)."""
        profiles_dir = self._user_profiles_dir(user_id)
        json_file = profiles_dir / f"{profile_id}.json"
        toon_file = profiles_dir / f"{profile_id}.toon"

        deleted = False
        if json_file.exists():
            json_file.unlink()
            deleted = True
        if toon_file.exists():
            toon_file.unlink()
            deleted = True

        if not deleted:
            return False
        
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
        """Parse resume into structured data.

        Two-phase approach:
        1. LLM extracts metadata (name, dates, companies, skills) — small output
        2. Raw text matching extracts full descriptions — no LLM truncation
        """
        # Phase 1: LLM extracts structure (short output — no descriptions)
        prompt = f"""Extract structured metadata from this resume. Do NOT include descriptions — just names, dates, and skills.

RESUME TEXT:
{text[:15000]}

OUTPUT FORMAT (JSON only):
{{
    "name": "Full Name",
    "email": "email or empty",
    "phone": "phone or empty",
    "location": "City, State/Country",
    "summary": "2-3 sentence professional summary",
    "skills": [
        {{"name": "Skill Name", "level": "expert|advanced|intermediate|beginner"}}
    ],
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "start_date": "YYYY-MM or YYYY",
            "end_date": "YYYY-MM or present",
            "description": ""
        }}
    ],
    "education": [
        {{"degree": "Degree Type", "field": "Field", "institution": "School", "year": "Year"}}
    ],
    "certifications": [
        {{"name": "Name", "issuer": "Org", "year": "Year or empty"}}
    ],
    "preferences": {{
        "target_roles": ["3-5 suggested job titles"],
        "remote_preference": "hybrid"
    }}
}}

RULES:
- Extract ALL skills (tools, languages, frameworks, methodologies)
- Extract ALL experience roles with exact titles, companies, and dates
- Leave description EMPTY (will be filled separately)
- Output ONLY valid JSON"""

        try:
            from job_agent_coordinator.services.llm_queue import llm_request, LLMQueue, Priority
            try:
                result = llm_request(
                    request_type="resume_parse",
                    model=PARSER_MODEL,
                    prompt=prompt,
                    options={"temperature": 0.1, "num_predict": 4000},
                    timeout=LLM_TIMEOUT,
                    priority=Priority.USER_INTERACTIVE,
                )
            except Exception as queue_err:
                logger.warning(f"Queue call failed ({queue_err}), calling Ollama directly")
                result = LLMQueue._call_ollama(
                    PARSER_MODEL, prompt, {"temperature": 0.1, "num_predict": 4000}, LLM_TIMEOUT
                )
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                parsed = json.loads(json_match.group())
                # Phase 2: Fill in descriptions from raw text
                self._fill_descriptions_from_text(parsed, text)
                return parsed
            else:
                logger.error("Could not find JSON in LLM response")
                return {}
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return {}

    @staticmethod
    def _fill_descriptions_from_text(parsed: dict, raw_text: str):
        """Extract full role descriptions from raw resume text.

        Strategy: find each company name in order, then grab all content
        lines (bullets, paragraphs) until the next company or section.
        Uses sequential search (search_from cursor) to handle duplicate
        company names correctly.
        """
        experiences = parsed.get("experience", [])
        if not experiences:
            return

        text_lower = raw_text.lower()

        # Build ordered list of anchor positions — find each role in sequence
        anchors = []  # [(start_idx, exp_index), ...]
        search_from = 0

        for i, exp in enumerate(experiences):
            company = (exp.get("company") or "").strip()
            title = (exp.get("title") or "").strip()
            if not company and not title:
                continue

            # Try multiple search strategies in order of specificity
            found = -1
            for marker in [
                title,                          # Full title
                f"{title.split()[0]} {company}" if title else company,  # First word of title + company
                company,                        # Just company name
            ]:
                if not marker:
                    continue
                idx = text_lower.find(marker.lower(), search_from)
                if idx >= 0:
                    found = idx
                    break

            if found >= 0:
                anchors.append((found, i))
                search_from = found + max(len(title), len(company), 10)

        if not anchors:
            return

        # Sort by position (should already be in order)
        anchors.sort(key=lambda x: x[0])

        # Section headers that end the experience section
        section_headers = ['education', 'skills', 'certifications', 'publications',
                          'awards', 'projects', 'languages', 'interests', 'references']

        # Extract text between each anchor
        for anchor_idx, (start_pos, exp_idx) in enumerate(anchors):
            # End is the next anchor, or end of text
            if anchor_idx + 1 < len(anchors):
                end_pos = anchors[anchor_idx + 1][0]
            else:
                end_pos = len(raw_text)

            # Also check for section headers
            for header in section_headers:
                h_idx = text_lower.find(header, start_pos + 20)
                if 0 < h_idx < end_pos:
                    end_pos = h_idx

            block = raw_text[start_pos:end_pos]

            # Extract content lines, skipping the header (title/company/date lines)
            desc_lines = []
            past_header = False
            for line in block.split('\n'):
                stripped = line.strip()
                if not stripped:
                    continue

                # Skip first few lines (title, company, location, date range)
                if not past_header:
                    title_lower = (experiences[exp_idx].get("title") or "").lower()
                    company_lower = (experiences[exp_idx].get("company") or "").lower()
                    if (title_lower[:15] in stripped.lower()
                            or company_lower in stripped.lower()
                            or len(stripped) < 30):
                        continue
                    past_header = True

                # Keep bullet points and substantial content lines
                if (stripped.startswith(('-', '•', '·', '*', '–', '►', '▪', '●'))
                        or len(stripped) > 20):
                    desc_lines.append(stripped)

            if desc_lines:
                experiences[exp_idx]["description"] = '\n'.join(desc_lines)
                logger.info(f"Extracted {len(desc_lines)} lines for {experiences[exp_idx].get('title','?')[:40]}")

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
