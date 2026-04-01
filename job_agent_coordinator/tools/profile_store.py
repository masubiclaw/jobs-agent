"""Profile storage for user job search profiles."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from google.adk.tools import FunctionTool
except ImportError:
    FunctionTool = lambda func: func

from .toon_format import to_toon, from_toon

logger = logging.getLogger(__name__)


class ProfileStore:
    """
    Persistent storage for user job search profiles.
    
    Features:
    - Store user info (name, contact, location)
    - Skills and experience tracking
    - Job preferences (roles, salary, location, remote)
    - Resume content storage
    - Multiple profile support
    """
    
    def __init__(self, storage_dir: Path = None):
        self.storage_dir = Path(storage_dir) if storage_dir else Path(".job_cache") / "profiles"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._profiles: Dict[str, Dict[str, Any]] = self._load_all()
        self._active_profile: Optional[str] = self._get_default_active()
        
        logger.info(f"👤 ProfileStore ready: {len(self._profiles)} profiles at {self.storage_dir}")
    
    def _load_all(self) -> Dict[str, Dict[str, Any]]:
        """Load all profiles from disk (TOON format with JSON fallback)."""
        profiles = {}
        
        # Load TOON files
        for f in self.storage_dir.glob("*.toon"):
            if f.name == "_meta.toon":
                continue
            try:
                data = from_toon(f.read_text())
                if data:
                    data["id"] = data.get("id", f.stem)
                    profiles[data["id"]] = data
            except Exception as e:
                logger.warning(f"Failed to load profile {f}: {e}")
        
        # Fallback: Load JSON files (for migration)
        for f in self.storage_dir.glob("*.json"):
            if f.name == "_meta.json":
                continue
            profile_id = f.stem
            if profile_id in profiles:
                continue  # Already loaded from TOON
            try:
                data = json.loads(f.read_text())
                profiles[data.get("id", f.stem)] = data
                logger.info(f"📦 Migrating profile {profile_id} from JSON to TOON...")
            except Exception as e:
                logger.warning(f"Failed to load profile {f}: {e}")
        
        return profiles
    
    def _get_default_active(self) -> Optional[str]:
        """Get default active profile."""
        # Try TOON meta file
        meta_file = self.storage_dir / "_meta.toon"
        if meta_file.exists():
            try:
                meta = from_toon(meta_file.read_text())
                return meta.get("active_profile")
            except:
                pass
        
        # Fallback: JSON meta file
        meta_json = self.storage_dir / "_meta.json"
        if meta_json.exists():
            try:
                meta = json.loads(meta_json.read_text())
                return meta.get("active_profile")
            except:
                pass
        
        # Return first profile if any
        return next(iter(self._profiles.keys()), None)
    
    def _save_profile(self, profile_id: str):
        """Save a profile to disk in TOON format."""
        if profile_id not in self._profiles:
            return
        
        profile = self._profiles[profile_id]
        profile["updated_at"] = datetime.now().isoformat()
        
        filepath = self.storage_dir / f"{profile_id}.toon"
        filepath.write_text(to_toon(profile) + '\n')
    
    def _save_meta(self):
        """Save metadata in TOON format."""
        meta_file = self.storage_dir / "_meta.toon"
        meta_file.write_text(to_toon({
            "active_profile": self._active_profile,
            "updated_at": datetime.now().isoformat(),
        }) + '\n')
    
    def create(
        self,
        name: str,
        email: str = "",
        phone: str = "",
        location: str = "",
        profile_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a new profile.
        
        Args:
            name: Full name
            email: Email address
            phone: Phone number
            location: Current location
            profile_id: Optional custom ID (defaults to sanitized name)
        
        Returns:
            The created profile
        """
        # Generate ID
        if not profile_id:
            profile_id = name.lower().replace(" ", "_").replace(".", "")[:20]
        
        # Check for existing
        if profile_id in self._profiles:
            logger.warning(f"Profile {profile_id} already exists, updating")
            return self.update(profile_id, name=name, email=email, phone=phone, location=location)
        
        profile = {
            "id": profile_id,
            "name": name,
            "email": email,
            "phone": phone,
            "location": location,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            
            # Skills & Experience
            "skills": [],
            "experience": [],
            "education": [],
            "certifications": [],
            
            # Job Preferences
            "preferences": {
                "target_roles": [],
                "target_locations": [],
                "remote_preference": "hybrid",  # remote, hybrid, onsite
                "salary_min": None,
                "salary_max": None,
                "job_types": ["full-time"],  # full-time, part-time, contract
                "industries": [],
                "excluded_companies": [],
            },
            
            # Resume
            "resume": {
                "summary": "",
                "content": "",
                "last_updated": None,
            },
            
            # Notes
            "notes": "",
        }
        
        self._profiles[profile_id] = profile
        self._save_profile(profile_id)
        
        # Set as active if first profile
        if len(self._profiles) == 1:
            self._active_profile = profile_id
            self._save_meta()
        
        logger.info(f"👤 Created profile: {name} ({profile_id})")
        return profile
    
    def get(self, profile_id: str = None) -> Optional[Dict[str, Any]]:
        """Get a profile by ID, or the active profile."""
        pid = profile_id or self._active_profile
        if not pid:
            return None
        return self._profiles.get(pid)
    
    def get_active(self) -> Optional[Dict[str, Any]]:
        """Get the active profile."""
        return self.get(self._active_profile)
    
    def set_active(self, profile_id: str) -> bool:
        """Set the active profile."""
        if profile_id not in self._profiles:
            return False
        self._active_profile = profile_id
        self._save_meta()
        logger.info(f"👤 Active profile: {profile_id}")
        return True
    
    def update(self, profile_id: str = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Update profile fields.
        
        Args:
            profile_id: Profile to update (or active profile)
            **kwargs: Fields to update (name, email, phone, location, notes)
        
        Returns:
            Updated profile or None
        """
        pid = profile_id or self._active_profile
        if not pid or pid not in self._profiles:
            return None
        
        profile = self._profiles[pid]
        
        # Update basic fields
        for field in ["name", "email", "phone", "location", "notes"]:
            if field in kwargs and kwargs[field] is not None:
                profile[field] = kwargs[field]
        
        self._save_profile(pid)
        logger.info(f"👤 Updated profile: {pid}")
        return profile
    
    def add_skill(self, skill: str, level: str = "intermediate", profile_id: str = None) -> List[Dict]:
        """
        Add a skill to the profile.
        
        Args:
            skill: Skill name
            level: beginner, intermediate, advanced, expert
            profile_id: Profile to update
        
        Returns:
            Updated skills list
        """
        pid = profile_id or self._active_profile
        if not pid or pid not in self._profiles:
            return []
        
        profile = self._profiles[pid]
        skills = profile.get("skills", [])
        
        # Check for existing
        for s in skills:
            if s.get("name", "").lower() == skill.lower():
                s["level"] = level
                self._save_profile(pid)
                return skills
        
        skills.append({
            "name": skill,
            "level": level,
            "added_at": datetime.now().isoformat(),
        })
        profile["skills"] = skills
        self._save_profile(pid)
        
        logger.info(f"➕ Added skill: {skill} ({level})")
        return skills
    
    def remove_skill(self, skill: str, profile_id: str = None) -> List[Dict]:
        """Remove a skill from the profile."""
        pid = profile_id or self._active_profile
        if not pid or pid not in self._profiles:
            return []
        
        profile = self._profiles[pid]
        profile["skills"] = [s for s in profile.get("skills", []) if s.get("name", "").lower() != skill.lower()]
        self._save_profile(pid)
        return profile["skills"]
    
    def add_experience(
        self,
        title: str,
        company: str,
        start_date: str,
        end_date: str = "present",
        description: str = "",
        profile_id: str = None
    ) -> List[Dict]:
        """
        Add work experience.
        
        Args:
            title: Job title
            company: Company name
            start_date: Start date (e.g., "2020-01")
            end_date: End date or "present"
            description: Role description
            profile_id: Profile to update
        
        Returns:
            Updated experience list
        """
        pid = profile_id or self._active_profile
        if not pid or pid not in self._profiles:
            return []
        
        profile = self._profiles[pid]
        experience = profile.get("experience", [])
        
        experience.append({
            "title": title,
            "company": company,
            "start_date": start_date,
            "end_date": end_date,
            "description": description,
            "added_at": datetime.now().isoformat(),
        })
        
        profile["experience"] = experience
        self._save_profile(pid)
        
        logger.info(f"➕ Added experience: {title} @ {company}")
        return experience
    
    def set_preferences(
        self,
        target_roles: List[str] = None,
        target_locations: List[str] = None,
        remote_preference: str = None,
        salary_min: int = None,
        salary_max: int = None,
        job_types: List[str] = None,
        excluded_companies: List[str] = None,
        profile_id: str = None
    ) -> Dict[str, Any]:
        """
        Update job search preferences.
        
        Args:
            target_roles: List of desired job titles
            target_locations: List of preferred locations
            remote_preference: remote, hybrid, or onsite
            salary_min: Minimum salary
            salary_max: Maximum salary
            job_types: full-time, part-time, contract
            excluded_companies: Companies to exclude
            profile_id: Profile to update
        
        Returns:
            Updated preferences
        """
        pid = profile_id or self._active_profile
        if not pid or pid not in self._profiles:
            return {}
        
        profile = self._profiles[pid]
        prefs = profile.get("preferences", {})
        
        if target_roles is not None:
            prefs["target_roles"] = target_roles
        if target_locations is not None:
            prefs["target_locations"] = target_locations
        if remote_preference is not None:
            prefs["remote_preference"] = remote_preference
        if salary_min is not None:
            prefs["salary_min"] = salary_min
        if salary_max is not None:
            prefs["salary_max"] = salary_max
        if job_types is not None:
            prefs["job_types"] = job_types
        if excluded_companies is not None:
            prefs["excluded_companies"] = [c.lower() for c in excluded_companies]
        
        profile["preferences"] = prefs
        self._save_profile(pid)
        
        logger.info(f"👤 Updated preferences for {pid}")
        return prefs
    
    def set_resume(self, summary: str = None, content: str = None, profile_id: str = None) -> Dict[str, Any]:
        """
        Update resume content.
        
        Args:
            summary: Brief professional summary
            content: Full resume text
            profile_id: Profile to update
        
        Returns:
            Updated resume section
        """
        pid = profile_id or self._active_profile
        if not pid or pid not in self._profiles:
            return {}
        
        profile = self._profiles[pid]
        resume = profile.get("resume", {})
        
        if summary is not None:
            resume["summary"] = summary
        if content is not None:
            resume["content"] = content
        resume["last_updated"] = datetime.now().isoformat()
        
        profile["resume"] = resume
        self._save_profile(pid)
        
        logger.info(f"📄 Updated resume for {pid}")
        return resume
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all profiles (summary only)."""
        return [
            {
                "id": p["id"],
                "name": p.get("name"),
                "location": p.get("location"),
                "skills_count": len(p.get("skills", [])),
                "is_active": p["id"] == self._active_profile,
            }
            for p in self._profiles.values()
        ]
    
    def delete(self, profile_id: str) -> bool:
        """Delete a profile."""
        if profile_id not in self._profiles:
            return False
        
        del self._profiles[profile_id]
        
        # Remove TOON file
        filepath = self.storage_dir / f"{profile_id}.toon"
        if filepath.exists():
            filepath.unlink()
        
        # Also remove JSON file if exists (migration cleanup)
        json_path = self.storage_dir / f"{profile_id}.json"
        if json_path.exists():
            json_path.unlink()
        
        # Update active if needed
        if self._active_profile == profile_id:
            self._active_profile = next(iter(self._profiles.keys()), None)
            self._save_meta()
        
        logger.info(f"🗑️ Deleted profile: {profile_id}")
        return True
    
    def get_search_context(self, profile_id: str = None) -> Dict[str, Any]:
        """
        Get profile context optimized for job search.
        Returns key info for the agent to use when searching.
        """
        profile = self.get(profile_id)
        if not profile:
            return {}
        
        prefs = profile.get("preferences", {})
        skills = [s.get("name") for s in profile.get("skills", [])]
        
        return {
            "name": profile.get("name"),
            "location": profile.get("location"),
            "skills": skills,
            "target_roles": prefs.get("target_roles", []),
            "target_locations": prefs.get("target_locations", []),
            "remote_preference": prefs.get("remote_preference"),
            "salary_range": f"${prefs.get('salary_min', 0):,} - ${prefs.get('salary_max', 0):,}" if prefs.get("salary_min") and prefs.get("salary_max") else None,
            "excluded_companies": prefs.get("excluded_companies", []),
            "resume_summary": profile.get("resume", {}).get("summary", ""),
        }


# Global store instance
_store: Optional[ProfileStore] = None


def get_store() -> ProfileStore:
    """Get or create the global profile store."""
    global _store
    if _store is None:
        _store = ProfileStore()
    return _store


# === FunctionTool wrappers ===

def create_profile(name: str, email: str = "", location: str = "") -> dict:
    """
    Create a new user profile for job searching.
    
    Args:
        name: Full name
        email: Email address
        location: Current location (city, state)
    
    Returns:
        Created profile summary
    """
    profile = get_store().create(name=name, email=email, location=location)
    return {
        "success": True,
        "profile_id": profile["id"],
        "name": profile["name"],
        "message": f"Created profile for {name}"
    }


def get_profile(profile_id: str = "") -> str:
    """
    Get a user profile.
    
    Args:
        profile_id: Profile ID (empty for active profile)
    
    Returns:
        TOON formatted profile data
    """
    profile = get_store().get(profile_id or None)
    if not profile:
        return "[profile]\nstatus: not found\naction: create a profile with create_profile"
    
    lines = [
        "[profile]",
        f"id: {profile.get('id', 'unknown')}",
        f"name: {profile.get('name', 'Unknown')}",
        f"email: {profile.get('email', 'not set')}",
        f"location: {profile.get('location', 'not set')}",
        f"created: {profile.get('created', 'unknown')}",
    ]
    
    # Skills
    skills = profile.get("skills", [])
    if skills:
        lines.extend(["", "[skills]"])
        for s in skills[:10]:
            level = s.get("level", "")
            lines.append(f"- {s.get('name', 'unknown')}: {level}")
    
    # Preferences
    prefs = profile.get("preferences", {})
    if prefs:
        lines.extend(["", "[preferences]"])
        if prefs.get("target_roles"):
            lines.append(f"target_roles: {', '.join(prefs['target_roles'])}")
        if prefs.get("target_locations"):
            lines.append(f"target_locations: {', '.join(prefs['target_locations'])}")
        if prefs.get("remote_preference"):
            lines.append(f"remote_preference: {prefs['remote_preference']}")
        if prefs.get("salary_min"):
            lines.append(f"salary_range: ${prefs.get('salary_min', 0):,} - ${prefs.get('salary_max', 0):,}")
        if prefs.get("excluded_companies"):
            lines.append(f"excluded_companies: {', '.join(prefs['excluded_companies'])}")
    
    # Resume summary
    resume = profile.get("resume", {})
    if resume.get("summary"):
        lines.extend(["", "[resume_summary]"])
        lines.append(resume["summary"][:200])
    
    return "\n".join(lines)


def update_profile(name: str = "", email: str = "", location: str = "", notes: str = "") -> dict:
    """
    Update the active profile.
    
    Args:
        name: New name (optional)
        email: New email (optional)
        location: New location (optional)
        notes: Additional notes (optional)
    
    Returns:
        Updated profile
    """
    kwargs = {}
    if name:
        kwargs["name"] = name
    if email:
        kwargs["email"] = email
    if location:
        kwargs["location"] = location
    if notes:
        kwargs["notes"] = notes
    
    profile = get_store().update(**kwargs)
    if not profile:
        return {"success": False, "error": "No active profile"}
    return {"success": True, "profile": profile}


def add_skill_to_profile(skill: str, level: str = "intermediate") -> dict:
    """
    Add a skill to the active profile.
    
    Args:
        skill: Skill name (e.g., "Python", "Machine Learning")
        level: beginner, intermediate, advanced, or expert
    
    Returns:
        Updated skills list
    """
    skills = get_store().add_skill(skill, level)
    return {"success": True, "skills": skills, "added": skill}


def set_job_preferences(
    target_roles: str = "",
    target_locations: str = "",
    remote_preference: str = "",
    salary_min: int = 0,
    salary_max: int = 0,
    excluded_companies: str = ""
) -> dict:
    """
    Set job search preferences.
    
    Args:
        target_roles: Comma-separated job titles (e.g., "Software Engineer, SWE, Developer")
        target_locations: Comma-separated locations (e.g., "Seattle, San Francisco, Remote")
        remote_preference: remote, hybrid, or onsite
        salary_min: Minimum salary
        salary_max: Maximum salary
        excluded_companies: Comma-separated companies to exclude
    
    Returns:
        Updated preferences
    """
    kwargs = {}
    if target_roles:
        kwargs["target_roles"] = [r.strip() for r in target_roles.split(",")]
    if target_locations:
        kwargs["target_locations"] = [l.strip() for l in target_locations.split(",")]
    if remote_preference:
        kwargs["remote_preference"] = remote_preference
    if salary_min:
        kwargs["salary_min"] = salary_min
    if salary_max:
        kwargs["salary_max"] = salary_max
    if excluded_companies:
        kwargs["excluded_companies"] = [c.strip() for c in excluded_companies.split(",")]
    
    prefs = get_store().set_preferences(**kwargs)
    return {"success": True, "preferences": prefs}


def set_resume_summary(summary: str) -> dict:
    """
    Set the professional summary for resume.
    
    Args:
        summary: Brief professional summary (2-3 sentences)
    
    Returns:
        Updated resume section
    """
    resume = get_store().set_resume(summary=summary)
    return {"success": True, "resume": resume}


def get_search_context() -> str:
    """
    Get profile context optimized for job searching.
    Returns skills, preferences, and other relevant info.
    """
    context = get_store().get_search_context()
    if not context:
        return "[search_context]\nstatus: no active profile\naction: create a profile first"
    
    lines = [
        "[search_context]",
        f"name: {context.get('name', 'Unknown')}",
        f"location: {context.get('location', 'not set')}",
    ]
    
    if context.get("skills"):
        lines.append(f"skills: {', '.join(context['skills'][:10])}")
    if context.get("target_roles"):
        lines.append(f"target_roles: {', '.join(context['target_roles'])}")
    if context.get("target_locations"):
        lines.append(f"target_locations: {', '.join(context['target_locations'])}")
    if context.get("remote_preference"):
        lines.append(f"remote_preference: {context['remote_preference']}")
    if context.get("salary_range"):
        lines.append(f"salary_range: {context['salary_range']}")
    if context.get("excluded_companies"):
        lines.append(f"excluded_companies: {', '.join(context['excluded_companies'])}")
    
    return "\n".join(lines)


def list_all_profiles() -> str:
    """List all stored profiles."""
    profiles = get_store().list_profiles()
    
    lines = [
        "[profiles]",
        f"total: {len(profiles)}",
        ""
    ]
    
    for p in profiles:
        lines.append(f"- {p.get('name', 'Unknown')} (id: {p.get('id', 'unknown')[:8]})")
        if p.get("email"):
            lines.append(f"  email: {p['email']}")
    
    if not profiles:
        lines.append("- no profiles found")
    
    return "\n".join(lines)


# Create FunctionTools
create_profile_tool = FunctionTool(func=create_profile)
get_profile_tool = FunctionTool(func=get_profile)
update_profile_tool = FunctionTool(func=update_profile)
add_skill_tool = FunctionTool(func=add_skill_to_profile)
set_preferences_tool = FunctionTool(func=set_job_preferences)
set_resume_tool = FunctionTool(func=set_resume_summary)
get_search_context_tool = FunctionTool(func=get_search_context)
list_profiles_tool = FunctionTool(func=list_all_profiles)
