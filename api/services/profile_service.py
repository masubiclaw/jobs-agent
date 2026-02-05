"""Profile service wrapping the existing ProfileStore with multi-user support."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from api.models import ProfileResponse, ProfileListItem, Skill, Experience, Preferences, Resume

# Import existing tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from job_agent_coordinator.tools.toon_format import to_toon, from_toon

logger = logging.getLogger(__name__)


class ProfileService:
    """
    Multi-user profile service.
    
    Stores profiles in user-specific directories:
    .job_cache/users/{user_id}/profiles/{profile_id}.toon
    """
    
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
            skills.append(Skill(
                name=s.get("name", ""),
                level=s.get("level", "intermediate"),
                added_at=datetime.fromisoformat(s["added_at"]) if s.get("added_at") else None
            ))
        
        # Parse experience
        experience = []
        for e in profile.get("experience", []):
            experience.append(Experience(
                title=e.get("title", ""),
                company=e.get("company", ""),
                start_date=e.get("start_date", ""),
                end_date=e.get("end_date", "present"),
                description=e.get("description", ""),
                added_at=datetime.fromisoformat(e["added_at"]) if e.get("added_at") else None
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
            email=profile.get("email", ""),
            phone=profile.get("phone", ""),
            location=profile.get("location", ""),
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
        location: str = ""
    ) -> Optional[ProfileResponse]:
        """Create a new profile."""
        # Generate ID
        profile_id = name.lower().replace(" ", "_").replace(".", "")[:20]
        
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
            "skills": [],
            "experience": [],
            "education": [],
            "certifications": [],
            "preferences": {
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
                profile[field] = kwargs[field]
        
        # Update skills
        if "skills" in kwargs and kwargs["skills"] is not None:
            profile["skills"] = [
                {
                    "name": s.name,
                    "level": s.level.value if hasattr(s.level, 'value') else s.level,
                    "added_at": s.added_at.isoformat() if s.added_at else datetime.now().isoformat()
                }
                for s in kwargs["skills"]
            ]
        
        # Update experience
        if "experience" in kwargs and kwargs["experience"] is not None:
            profile["experience"] = [
                {
                    "title": e.title,
                    "company": e.company,
                    "start_date": e.start_date,
                    "end_date": e.end_date,
                    "description": e.description,
                    "added_at": e.added_at.isoformat() if e.added_at else datetime.now().isoformat()
                }
                for e in kwargs["experience"]
            ]
        
        # Update preferences
        if "preferences" in kwargs and kwargs["preferences"] is not None:
            prefs = kwargs["preferences"]
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
