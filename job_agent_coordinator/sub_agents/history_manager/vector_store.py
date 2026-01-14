"""Vector store for job search history using ChromaDB."""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional ChromaDB import - fallback to in-memory if not available
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB not installed. Using in-memory storage. Install with: pip install chromadb")


class JobSearchVectorStore:
    """
    Vector store for persisting job search history.
    
    Collections:
    - job_postings: Analyzed job postings
    - resumes: Generated/reviewed resumes
    - resume_versions: Different versions of resumes with descriptors
    - cover_letters: Generated cover letters
    - user_profiles: User profile information for matching
    - company_analyses: Company research results
    - search_sessions: Job search sessions and results
    - search_criteria: Saved search filters/preferences for reuse
    - resume_templates: Resume formatting templates and styling preferences
    - design_instructions: Explicit instructions and guard rails for application design
    - response_cache: Cached agent responses to avoid re-analysis
    - search_results_cache: Cached search results with source links
    """
    
    # Cache expiry times (in hours)
    CACHE_EXPIRY_HOURS = {
        "search_results": 24,      # Search results expire after 24 hours
        "job_analysis": 168,       # Job analysis expires after 7 days
        "company_analysis": 168,   # Company analysis expires after 7 days
        "market_analysis": 72,     # Market analysis expires after 3 days
        "default": 48,             # Default expiry 2 days
    }
    
    def __init__(self, persist_directory: Optional[str] = None):
        """
        Initialize the vector store.
        
        Args:
            persist_directory: Directory to persist data. If None, uses default.
        """
        self.persist_directory = persist_directory or os.path.join(
            os.path.expanduser("~"), ".job_agent_coordinator", "history"
        )
        
        if CHROMADB_AVAILABLE:
            os.makedirs(self.persist_directory, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            self._init_collections()
            logger.info(f"✅ ChromaDB initialized at {self.persist_directory}")
        else:
            # Fallback to simple in-memory dict storage
            self.client = None
            self._memory_store = {
                "job_postings": [],
                "resumes": [],
                "resume_versions": [],
                "cover_letters": [],
                "user_profiles": [],
                "company_analyses": [],
                "search_sessions": [],
                "search_criteria": [],
                "resume_templates": [],
                "design_instructions": [],
                "response_cache": [],
                "search_results_cache": []
            }
            logger.info("⚠️ Using in-memory storage (ChromaDB not available)")
    
    def _init_collections(self):
        """Initialize ChromaDB collections."""
        self.job_postings = self.client.get_or_create_collection(
            name="job_postings",
            metadata={"description": "Analyzed job postings"}
        )
        self.resumes = self.client.get_or_create_collection(
            name="resumes",
            metadata={"description": "Generated and reviewed resumes"}
        )
        self.resume_versions = self.client.get_or_create_collection(
            name="resume_versions",
            metadata={"description": "Different versions of resumes with descriptors"}
        )
        self.cover_letters = self.client.get_or_create_collection(
            name="cover_letters",
            metadata={"description": "Generated cover letters"}
        )
        self.user_profiles = self.client.get_or_create_collection(
            name="user_profiles",
            metadata={"description": "User profile information for job matching"}
        )
        self.company_analyses = self.client.get_or_create_collection(
            name="company_analyses",
            metadata={"description": "Company research and analysis"}
        )
        self.search_sessions = self.client.get_or_create_collection(
            name="search_sessions",
            metadata={"description": "Job search sessions and results"}
        )
        self.search_criteria_collection = self.client.get_or_create_collection(
            name="search_criteria",
            metadata={"description": "Saved job search criteria/filters for reuse"}
        )
        self.resume_templates = self.client.get_or_create_collection(
            name="resume_templates",
            metadata={"description": "Resume formatting templates and styling preferences"}
        )
        self.design_instructions = self.client.get_or_create_collection(
            name="design_instructions",
            metadata={"description": "Explicit instructions and guard rails for application design"}
        )
        self.response_cache = self.client.get_or_create_collection(
            name="response_cache",
            metadata={"description": "Cached agent responses to avoid re-analysis"}
        )
        self.search_results_cache = self.client.get_or_create_collection(
            name="search_results_cache",
            metadata={"description": "Cached search results with source links"}
        )
    
    # =========================================================================
    # Job Postings
    # =========================================================================
    
    def save_job_posting(
        self,
        title: str,
        company: str,
        content: str,
        analysis: str,
        url: Optional[str] = None,
        match_score: Optional[float] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save an analyzed job posting.
        
        Returns:
            ID of the saved posting
        """
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        doc_metadata = {
            "title": title,
            "company": company,
            "url": url or "",
            "match_score": match_score or 0.0,
            "timestamp": timestamp,
            "type": "job_posting",
            **(metadata or {})
        }
        
        combined_text = f"Job: {title} at {company}\n\n{content}\n\nAnalysis:\n{analysis}"
        
        if CHROMADB_AVAILABLE:
            self.job_postings.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            self._memory_store["job_postings"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved job posting: {title} at {company} (ID: {doc_id})")
        return doc_id
    
    def search_job_postings(
        self,
        query: str,
        n_results: int = 5,
        company_filter: Optional[str] = None
    ) -> list[dict]:
        """Search similar job postings."""
        if CHROMADB_AVAILABLE:
            where_filter = {"company": company_filter} if company_filter else None
            results = self.job_postings.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            return self._format_results(results)
        else:
            # Simple keyword search for in-memory
            return self._memory_search("job_postings", query, n_results)
    
    def get_recent_job_postings(self, limit: int = 10) -> list[dict]:
        """Get most recent job postings."""
        if CHROMADB_AVAILABLE:
            results = self.job_postings.get(
                limit=limit,
                include=["documents", "metadatas"]
            )
            return self._format_get_results(results)
        else:
            return self._memory_store["job_postings"][-limit:]
    
    # =========================================================================
    # Resumes
    # =========================================================================
    
    def save_resume(
        self,
        target_role: str,
        target_company: Optional[str],
        resume_content: str,
        source_profile: str,
        optimization_score: Optional[float] = None,
        job_posting_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save a generated resume.
        
        Args:
            target_role: Role the resume is tailored for
            target_company: Company (if specific)
            resume_content: The resume content
            source_profile: Original profile used as source
            optimization_score: How well optimized
            job_posting_id: Linked job posting ID
            metadata: Additional metadata
        
        Returns:
            ID of the saved resume
        """
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        doc_metadata = {
            "target_role": target_role,
            "target_company": target_company or "General",
            "optimization_score": optimization_score or 0.0,
            "job_posting_id": job_posting_id or "",
            "timestamp": timestamp,
            "type": "resume"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        combined_text = f"Resume for: {target_role}\nCompany: {target_company or 'General'}\n\n{resume_content}\n\nSource Profile:\n{source_profile}"
        
        if CHROMADB_AVAILABLE:
            self.resumes.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            self._memory_store["resumes"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved resume for: {target_role} (ID: {doc_id})")
        return doc_id
    
    def search_resumes(
        self,
        query: str,
        n_results: int = 5,
        role_filter: Optional[str] = None
    ) -> list[dict]:
        """Search similar resumes."""
        if CHROMADB_AVAILABLE:
            where_filter = {"target_role": role_filter} if role_filter else None
            results = self.resumes.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            return self._format_results(results)
        else:
            return self._memory_search("resumes", query, n_results)
    
    def get_resumes_for_role(self, role: str, limit: int = 5) -> list[dict]:
        """Get resumes created for a specific role."""
        if CHROMADB_AVAILABLE:
            results = self.resumes.get(
                where={"target_role": {"$contains": role}},
                limit=limit,
                include=["documents", "metadatas"]
            )
            return self._format_get_results(results)
        else:
            return [
                r for r in self._memory_store["resumes"]
                if role.lower() in r.get("metadata", {}).get("target_role", "").lower()
            ][:limit]
    
    # =========================================================================
    # Resume Versions (Application Designer Storage)
    # =========================================================================
    
    def save_resume_version(
        self,
        version_name: str,
        target_role: str,
        target_company: Optional[str],
        resume_content: str,
        version_descriptor: str,
        base_profile_id: Optional[str] = None,
        job_posting_id: Optional[str] = None,
        is_master: bool = False,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save a resume version with descriptor.
        
        Args:
            version_name: Name for this version (e.g., "Technical Focus", "Leadership Focus")
            target_role: Target job role
            target_company: Target company (if specific)
            resume_content: The resume content
            version_descriptor: Description of what makes this version unique
            base_profile_id: ID of the user profile this is based on
            job_posting_id: ID of the job posting this was tailored for
            is_master: Whether this is the master/base resume
            metadata: Additional metadata
        
        Returns:
            ID of the saved resume version
        """
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        doc_metadata = {
            "version_name": version_name,
            "target_role": target_role,
            "target_company": target_company or "General",
            "version_descriptor": version_descriptor,
            "base_profile_id": base_profile_id or "",
            "job_posting_id": job_posting_id or "",
            "is_master": is_master,
            "timestamp": timestamp,
            "type": "resume_version"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        combined_text = f"Resume Version: {version_name}\nRole: {target_role}\nCompany: {target_company or 'General'}\nDescriptor: {version_descriptor}\n\n{resume_content}"
        
        if CHROMADB_AVAILABLE:
            self.resume_versions.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            self._memory_store["resume_versions"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved resume version: {version_name} for {target_role} (ID: {doc_id})")
        return doc_id
    
    def get_resume_versions(
        self,
        target_role: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """Get resume versions, optionally filtered by role."""
        if CHROMADB_AVAILABLE:
            if target_role:
                results = self.resume_versions.get(
                    where={"target_role": {"$contains": target_role}},
                    limit=limit,
                    include=["documents", "metadatas"]
                )
            else:
                results = self.resume_versions.get(
                    limit=limit,
                    include=["documents", "metadatas"]
                )
            return self._format_get_results(results)
        else:
            versions = self._memory_store["resume_versions"]
            if target_role:
                versions = [v for v in versions if target_role.lower() in v.get("metadata", {}).get("target_role", "").lower()]
            return versions[-limit:]
    
    def get_master_resume(self) -> Optional[dict]:
        """Get the master/base resume version."""
        if CHROMADB_AVAILABLE:
            results = self.resume_versions.get(
                where={"is_master": True},
                limit=1,
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            return formatted[0] if formatted else None
        else:
            masters = [v for v in self._memory_store["resume_versions"] if v.get("metadata", {}).get("is_master")]
            return masters[-1] if masters else None
    
    def search_resume_versions(
        self,
        query: str,
        n_results: int = 5
    ) -> list[dict]:
        """Search resume versions by content/descriptor."""
        if CHROMADB_AVAILABLE:
            results = self.resume_versions.query(
                query_texts=[query],
                n_results=n_results
            )
            return self._format_results(results)
        else:
            return self._memory_search("resume_versions", query, n_results)
    
    def list_resume_versions(self) -> list[dict]:
        """List all resume versions with their descriptors."""
        if CHROMADB_AVAILABLE:
            results = self.resume_versions.get(
                include=["metadatas"]
            )
            if results and results.get("ids"):
                return [
                    {
                        "id": id_,
                        "version_name": meta.get("version_name"),
                        "target_role": meta.get("target_role"),
                        "target_company": meta.get("target_company"),
                        "version_descriptor": meta.get("version_descriptor"),
                        "is_master": meta.get("is_master"),
                        "timestamp": meta.get("timestamp")
                    }
                    for id_, meta in zip(results["ids"], results["metadatas"])
                ]
            return []
        else:
            return [
                {
                    "id": v["id"],
                    **{k: v["metadata"].get(k) for k in ["version_name", "target_role", "target_company", "version_descriptor", "is_master", "timestamp"]}
                }
                for v in self._memory_store["resume_versions"]
            ]
    
    # =========================================================================
    # Cover Letters (Application Designer Storage)
    # =========================================================================
    
    def save_cover_letter(
        self,
        target_role: str,
        target_company: str,
        cover_letter_content: str,
        job_posting_id: Optional[str] = None,
        resume_version_id: Optional[str] = None,
        key_highlights: Optional[list[str]] = None,
        tone: Optional[str] = None,  # "formal", "conversational", "enthusiastic"
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save a cover letter.
        
        Args:
            target_role: Target job role
            target_company: Target company
            cover_letter_content: The cover letter content
            job_posting_id: ID of the job posting this was written for
            resume_version_id: ID of the resume version this accompanies
            key_highlights: Key points/achievements highlighted
            tone: Tone of the letter
            metadata: Additional metadata
        
        Returns:
            ID of the saved cover letter
        """
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        doc_metadata = {
            "target_role": target_role,
            "target_company": target_company,
            "job_posting_id": job_posting_id or "",
            "resume_version_id": resume_version_id or "",
            "key_highlights": json.dumps(key_highlights or []),
            "tone": tone or "professional",
            "timestamp": timestamp,
            "type": "cover_letter"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        combined_text = f"Cover Letter for: {target_role} at {target_company}\nTone: {tone or 'professional'}\n\n{cover_letter_content}"
        
        if CHROMADB_AVAILABLE:
            self.cover_letters.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            self._memory_store["cover_letters"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved cover letter for: {target_role} at {target_company} (ID: {doc_id})")
        return doc_id
    
    def get_cover_letters_for_company(
        self,
        company: str,
        limit: int = 5
    ) -> list[dict]:
        """Get cover letters for a specific company."""
        if CHROMADB_AVAILABLE:
            results = self.cover_letters.get(
                where={"target_company": company},
                limit=limit,
                include=["documents", "metadatas"]
            )
            return self._format_get_results(results)
        else:
            return [
                cl for cl in self._memory_store["cover_letters"]
                if cl.get("metadata", {}).get("target_company", "").lower() == company.lower()
            ][:limit]
    
    def search_cover_letters(
        self,
        query: str,
        n_results: int = 5
    ) -> list[dict]:
        """Search cover letters."""
        if CHROMADB_AVAILABLE:
            results = self.cover_letters.query(
                query_texts=[query],
                n_results=n_results
            )
            return self._format_results(results)
        else:
            return self._memory_search("cover_letters", query, n_results)
    
    def get_recent_cover_letters(self, limit: int = 10) -> list[dict]:
        """Get most recent cover letters."""
        if CHROMADB_AVAILABLE:
            results = self.cover_letters.get(
                limit=limit,
                include=["documents", "metadatas"]
            )
            return self._format_get_results(results)
        else:
            return self._memory_store["cover_letters"][-limit:]
    
    # =========================================================================
    # User Profiles (Profile Analyst Storage)
    # =========================================================================
    
    def save_user_profile(
        self,
        name: str,
        profile_content: str,
        skills: Optional[list[str]] = None,
        experience_years: Optional[int] = None,
        current_role: Optional[str] = None,
        target_roles: Optional[list[str]] = None,
        education: Optional[list[str]] = None,
        certifications: Optional[list[str]] = None,
        achievements: Optional[list[str]] = None,
        values: Optional[list[str]] = None,
        work_preferences: Optional[dict] = None,
        is_primary: bool = False,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save a user profile.
        
        Args:
            name: Profile name/identifier (e.g., "Full Profile", "Technical Summary")
            profile_content: Full profile content/text
            skills: List of skills
            experience_years: Years of experience
            current_role: Current job role
            target_roles: Desired roles
            education: Education entries
            certifications: Certifications
            achievements: Key achievements
            values: Personal/professional values
            work_preferences: Dict with remote, location, salary preferences
            is_primary: Whether this is the primary profile
            metadata: Additional metadata
        
        Returns:
            ID of the saved profile
        """
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        doc_metadata = {
            "name": name,
            "experience_years": experience_years or 0,
            "current_role": current_role or "",
            "target_roles": json.dumps(target_roles or []),
            "skills": json.dumps(skills or []),
            "education": json.dumps(education or []),
            "certifications": json.dumps(certifications or []),
            "achievements": json.dumps(achievements or []),
            "values": json.dumps(values or []),
            "work_preferences": json.dumps(work_preferences or {}),
            "is_primary": is_primary,
            "timestamp": timestamp,
            "type": "user_profile"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        combined_text = f"Profile: {name}\nCurrent Role: {current_role or 'N/A'}\nExperience: {experience_years or 0} years\nSkills: {', '.join(skills or [])}\n\n{profile_content}"
        
        if CHROMADB_AVAILABLE:
            # If setting as primary, unset other primaries first
            if is_primary:
                self._unset_primary_profile()
            
            self.user_profiles.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            if is_primary:
                for item in self._memory_store["user_profiles"]:
                    item["metadata"]["is_primary"] = False
            
            self._memory_store["user_profiles"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved user profile: {name} (ID: {doc_id})")
        return doc_id
    
    def _unset_primary_profile(self):
        """Unset is_primary flag on all existing profiles."""
        if CHROMADB_AVAILABLE:
            existing = self.user_profiles.get(
                where={"is_primary": True},
                include=["metadatas"]
            )
            if existing and existing.get("ids"):
                for id_, meta in zip(existing["ids"], existing["metadatas"]):
                    meta["is_primary"] = False
                    self.user_profiles.update(
                        ids=[id_],
                        metadatas=[meta]
                    )
    
    def get_primary_profile(self) -> Optional[dict]:
        """Get the primary user profile."""
        if CHROMADB_AVAILABLE:
            results = self.user_profiles.get(
                where={"is_primary": True},
                limit=1,
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            return formatted[0] if formatted else None
        else:
            primaries = [p for p in self._memory_store["user_profiles"] if p.get("metadata", {}).get("is_primary")]
            return primaries[-1] if primaries else None
    
    def get_user_profile(self, profile_id: str) -> Optional[dict]:
        """Get a specific user profile by ID."""
        if CHROMADB_AVAILABLE:
            results = self.user_profiles.get(
                ids=[profile_id],
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            return formatted[0] if formatted else None
        else:
            for p in self._memory_store["user_profiles"]:
                if p["id"] == profile_id:
                    return p
            return None
    
    def list_user_profiles(self) -> list[dict]:
        """List all user profiles."""
        if CHROMADB_AVAILABLE:
            results = self.user_profiles.get(
                include=["metadatas"]
            )
            if results and results.get("ids"):
                return [
                    {
                        "id": id_,
                        "name": meta.get("name"),
                        "current_role": meta.get("current_role"),
                        "experience_years": meta.get("experience_years"),
                        "is_primary": meta.get("is_primary"),
                        "timestamp": meta.get("timestamp")
                    }
                    for id_, meta in zip(results["ids"], results["metadatas"])
                ]
            return []
        else:
            return [
                {
                    "id": p["id"],
                    **{k: p["metadata"].get(k) for k in ["name", "current_role", "experience_years", "is_primary", "timestamp"]}
                }
                for p in self._memory_store["user_profiles"]
            ]
    
    def update_user_profile(
        self,
        profile_id: str,
        **updates
    ) -> bool:
        """Update a user profile."""
        if CHROMADB_AVAILABLE:
            existing = self.user_profiles.get(
                ids=[profile_id],
                include=["documents", "metadatas"]
            )
            if not existing or not existing.get("ids"):
                return False
            
            meta = existing["metadatas"][0]
            doc = existing["documents"][0]
            
            # Handle is_primary flag
            if updates.get("is_primary"):
                self._unset_primary_profile()
            
            # Update metadata
            for key, value in updates.items():
                if key in ["skills", "education", "certifications", "achievements", "values", "target_roles"]:
                    meta[key] = json.dumps(value) if isinstance(value, list) else value
                elif key == "work_preferences":
                    meta[key] = json.dumps(value) if isinstance(value, dict) else value
                elif key == "profile_content":
                    doc = value
                else:
                    meta[key] = value
            
            meta["timestamp"] = datetime.now().isoformat()
            
            self.user_profiles.update(
                ids=[profile_id],
                documents=[doc],
                metadatas=[meta]
            )
            logger.info(f"Updated user profile: {profile_id}")
            return True
        else:
            for p in self._memory_store["user_profiles"]:
                if p["id"] == profile_id:
                    if updates.get("is_primary"):
                        for other in self._memory_store["user_profiles"]:
                            other["metadata"]["is_primary"] = False
                    for key, value in updates.items():
                        if key == "profile_content":
                            p["document"] = value
                        else:
                            p["metadata"][key] = value
                    p["metadata"]["timestamp"] = datetime.now().isoformat()
                    return True
            return False
    
    def delete_user_profile(self, profile_id: str) -> bool:
        """Delete a user profile."""
        if CHROMADB_AVAILABLE:
            try:
                self.user_profiles.delete(ids=[profile_id])
                logger.info(f"Deleted user profile: {profile_id}")
                return True
            except Exception:
                return False
        else:
            original_len = len(self._memory_store["user_profiles"])
            self._memory_store["user_profiles"] = [
                p for p in self._memory_store["user_profiles"] if p["id"] != profile_id
            ]
            return len(self._memory_store["user_profiles"]) < original_len
    
    def search_user_profiles(
        self,
        query: str,
        n_results: int = 5
    ) -> list[dict]:
        """Search user profiles."""
        if CHROMADB_AVAILABLE:
            results = self.user_profiles.query(
                query_texts=[query],
                n_results=n_results
            )
            return self._format_results(results)
        else:
            return self._memory_search("user_profiles", query, n_results)
    
    # =========================================================================
    # Company Analyses
    # =========================================================================
    
    def save_company_analysis(
        self,
        company_name: str,
        analysis: str,
        rating: Optional[float] = None,
        values: Optional[list[str]] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """Save a company analysis."""
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        doc_metadata = {
            "company_name": company_name,
            "rating": rating or 0.0,
            "values": json.dumps(values or []),
            "timestamp": timestamp,
            "type": "company_analysis"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        if CHROMADB_AVAILABLE:
            self.company_analyses.add(
                ids=[doc_id],
                documents=[f"Company: {company_name}\n\n{analysis}"],
                metadatas=[doc_metadata]
            )
        else:
            self._memory_store["company_analyses"].append({
                "id": doc_id,
                "document": f"Company: {company_name}\n\n{analysis}",
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved company analysis: {company_name} (ID: {doc_id})")
        return doc_id
    
    def get_company_analysis(self, company_name: str) -> Optional[dict]:
        """Get most recent analysis for a company."""
        if CHROMADB_AVAILABLE:
            results = self.company_analyses.get(
                where={"company_name": company_name},
                limit=1,
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            return formatted[0] if formatted else None
        else:
            matches = [
                c for c in self._memory_store["company_analyses"]
                if c.get("metadata", {}).get("company_name", "").lower() == company_name.lower()
            ]
            return matches[-1] if matches else None
    
    def search_company_analyses(
        self,
        query: str,
        n_results: int = 5
    ) -> list[dict]:
        """Search company analyses."""
        if CHROMADB_AVAILABLE:
            results = self.company_analyses.query(
                query_texts=[query],
                n_results=n_results
            )
            return self._format_results(results)
        else:
            return self._memory_search("company_analyses", query, n_results)
    
    # =========================================================================
    # Search Sessions
    # =========================================================================
    
    def save_search_session(
        self,
        search_criteria: dict,
        results_summary: str,
        job_count: int,
        top_matches: list[dict],
        metadata: Optional[dict] = None
    ) -> str:
        """Save a job search session."""
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        criteria_str = json.dumps(search_criteria)
        matches_str = json.dumps(top_matches[:10])  # Store top 10
        
        doc_metadata = {
            "search_criteria": criteria_str,
            "job_count": job_count,
            "timestamp": timestamp,
            "type": "search_session"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        combined_text = f"Search: {criteria_str}\n\nResults ({job_count} jobs):\n{results_summary}\n\nTop Matches:\n{matches_str}"
        
        if CHROMADB_AVAILABLE:
            self.search_sessions.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            self._memory_store["search_sessions"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved search session (ID: {doc_id})")
        return doc_id
    
    # =========================================================================
    # Resume Templates (Application Designer Storage)
    # =========================================================================
    
    def save_resume_template(
        self,
        name: str,
        description: str,
        template_type: str,  # "professional", "compact", "leadership", "technical", "custom"
        styles: dict,  # font sizes, margins, spacing
        sections_order: list[str],
        section_formatting: Optional[dict] = None,
        is_default: bool = False,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save a resume template/formatting configuration.
        
        Args:
            name: Template name (e.g., "Professional", "Technical Focus")
            description: Description of when to use this template
            template_type: Type category
            styles: Dict with header_size, section_size, body_size, line_spacing, margins
            sections_order: List of section names in order
            section_formatting: Dict with per-section formatting rules
            is_default: Whether this is the default template
            metadata: Additional metadata
        
        Returns:
            ID of the saved template
        """
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        doc_metadata = {
            "name": name,
            "description": description,
            "template_type": template_type,
            "styles_json": json.dumps(styles),
            "sections_order": json.dumps(sections_order),
            "section_formatting": json.dumps(section_formatting or {}),
            "is_default": is_default,
            "timestamp": timestamp,
            "type": "resume_template"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        combined_text = f"Resume Template: {name}\nType: {template_type}\nDescription: {description}\nSections: {', '.join(sections_order)}"
        
        if CHROMADB_AVAILABLE:
            if is_default:
                self._unset_default_template()
            
            self.resume_templates.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            if is_default:
                for item in self._memory_store["resume_templates"]:
                    item["metadata"]["is_default"] = False
            
            self._memory_store["resume_templates"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved resume template: {name} (ID: {doc_id})")
        return doc_id
    
    def _unset_default_template(self):
        """Unset is_default flag on all existing templates."""
        if CHROMADB_AVAILABLE:
            existing = self.resume_templates.get(
                where={"is_default": True},
                include=["metadatas"]
            )
            if existing and existing.get("ids"):
                for id_, meta in zip(existing["ids"], existing["metadatas"]):
                    meta["is_default"] = False
                    self.resume_templates.update(
                        ids=[id_],
                        metadatas=[meta]
                    )
    
    def get_resume_template(self, template_id: str) -> Optional[dict]:
        """Get a specific resume template by ID."""
        if CHROMADB_AVAILABLE:
            results = self.resume_templates.get(
                ids=[template_id],
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            if formatted:
                result = formatted[0]
                result["styles"] = json.loads(result.get("metadata", {}).get("styles_json", "{}"))
                result["sections_order"] = json.loads(result.get("metadata", {}).get("sections_order", "[]"))
                return result
            return None
        else:
            for t in self._memory_store["resume_templates"]:
                if t["id"] == template_id:
                    result = t.copy()
                    result["styles"] = json.loads(result["metadata"].get("styles_json", "{}"))
                    result["sections_order"] = json.loads(result["metadata"].get("sections_order", "[]"))
                    return result
            return None
    
    def get_default_resume_template(self) -> Optional[dict]:
        """Get the default resume template."""
        if CHROMADB_AVAILABLE:
            results = self.resume_templates.get(
                where={"is_default": True},
                limit=1,
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            if formatted:
                result = formatted[0]
                result["styles"] = json.loads(result.get("metadata", {}).get("styles_json", "{}"))
                result["sections_order"] = json.loads(result.get("metadata", {}).get("sections_order", "[]"))
                return result
            return None
        else:
            defaults = [t for t in self._memory_store["resume_templates"] if t.get("metadata", {}).get("is_default")]
            if defaults:
                result = defaults[-1].copy()
                result["styles"] = json.loads(result["metadata"].get("styles_json", "{}"))
                result["sections_order"] = json.loads(result["metadata"].get("sections_order", "[]"))
                return result
            return None
    
    def list_resume_templates(self) -> list[dict]:
        """List all resume templates."""
        if CHROMADB_AVAILABLE:
            results = self.resume_templates.get(
                include=["metadatas"]
            )
            if results and results.get("ids"):
                return [
                    {
                        "id": id_,
                        "name": meta.get("name"),
                        "description": meta.get("description"),
                        "template_type": meta.get("template_type"),
                        "is_default": meta.get("is_default"),
                        "timestamp": meta.get("timestamp")
                    }
                    for id_, meta in zip(results["ids"], results["metadatas"])
                ]
            return []
        else:
            return [
                {
                    "id": t["id"],
                    **{k: t["metadata"].get(k) for k in ["name", "description", "template_type", "is_default", "timestamp"]}
                }
                for t in self._memory_store["resume_templates"]
            ]
    
    def delete_resume_template(self, template_id: str) -> bool:
        """Delete a resume template."""
        if CHROMADB_AVAILABLE:
            try:
                self.resume_templates.delete(ids=[template_id])
                logger.info(f"Deleted resume template: {template_id}")
                return True
            except Exception:
                return False
        else:
            original_len = len(self._memory_store["resume_templates"])
            self._memory_store["resume_templates"] = [
                t for t in self._memory_store["resume_templates"] if t["id"] != template_id
            ]
            return len(self._memory_store["resume_templates"]) < original_len
    
    # =========================================================================
    # Design Instructions (Guard Rails & Requirements)
    # =========================================================================
    
    def save_design_instruction(
        self,
        name: str,
        instruction_type: str,  # "guard_rail", "requirement", "formatting", "content"
        instruction_text: str,
        applies_to: list[str],  # ["resume", "cover_letter", "both"]
        priority: str = "medium",  # "critical", "high", "medium", "low"
        is_active: bool = True,
        source_verification_required: bool = False,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save a design instruction or guard rail.
        
        Args:
            name: Instruction name (e.g., "No Fabricated Experience")
            instruction_type: Category of instruction
            instruction_text: The actual instruction/rule
            applies_to: What documents this applies to
            priority: Importance level
            is_active: Whether currently active
            source_verification_required: If claims must be traced to source
            metadata: Additional metadata
        
        Returns:
            ID of the saved instruction
        """
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        doc_metadata = {
            "name": name,
            "instruction_type": instruction_type,
            "applies_to": json.dumps(applies_to),
            "priority": priority,
            "is_active": is_active,
            "source_verification_required": source_verification_required,
            "timestamp": timestamp,
            "type": "design_instruction"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        combined_text = f"Instruction: {name}\nType: {instruction_type}\nPriority: {priority}\nApplies to: {', '.join(applies_to)}\n\n{instruction_text}"
        
        if CHROMADB_AVAILABLE:
            self.design_instructions.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            self._memory_store["design_instructions"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved design instruction: {name} (ID: {doc_id})")
        return doc_id
    
    def get_active_instructions(
        self,
        applies_to: Optional[str] = None,  # "resume", "cover_letter", or None for all
        instruction_type: Optional[str] = None
    ) -> list[dict]:
        """Get all active design instructions, optionally filtered."""
        if CHROMADB_AVAILABLE:
            # Build where filter
            where_filter = {"is_active": True}
            if instruction_type:
                where_filter["instruction_type"] = instruction_type
            
            results = self.design_instructions.get(
                where=where_filter,
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            
            # Filter by applies_to if specified
            if applies_to:
                formatted = [
                    r for r in formatted
                    if applies_to in json.loads(r.get("metadata", {}).get("applies_to", "[]"))
                    or "both" in json.loads(r.get("metadata", {}).get("applies_to", "[]"))
                ]
            
            return formatted
        else:
            results = [
                i for i in self._memory_store["design_instructions"]
                if i.get("metadata", {}).get("is_active", True)
            ]
            if instruction_type:
                results = [r for r in results if r.get("metadata", {}).get("instruction_type") == instruction_type]
            if applies_to:
                results = [
                    r for r in results
                    if applies_to in json.loads(r.get("metadata", {}).get("applies_to", "[]"))
                    or "both" in json.loads(r.get("metadata", {}).get("applies_to", "[]"))
                ]
            return results
    
    def get_guard_rails(self, applies_to: Optional[str] = None) -> list[dict]:
        """Get all active guard rail instructions."""
        return self.get_active_instructions(applies_to=applies_to, instruction_type="guard_rail")
    
    def get_requirements(self, applies_to: Optional[str] = None) -> list[dict]:
        """Get all active requirement instructions."""
        return self.get_active_instructions(applies_to=applies_to, instruction_type="requirement")
    
    def list_design_instructions(self) -> list[dict]:
        """List all design instructions."""
        if CHROMADB_AVAILABLE:
            results = self.design_instructions.get(
                include=["metadatas"]
            )
            if results and results.get("ids"):
                return [
                    {
                        "id": id_,
                        "name": meta.get("name"),
                        "instruction_type": meta.get("instruction_type"),
                        "priority": meta.get("priority"),
                        "is_active": meta.get("is_active"),
                        "applies_to": json.loads(meta.get("applies_to", "[]")),
                        "timestamp": meta.get("timestamp")
                    }
                    for id_, meta in zip(results["ids"], results["metadatas"])
                ]
            return []
        else:
            return [
                {
                    "id": i["id"],
                    "name": i["metadata"].get("name"),
                    "instruction_type": i["metadata"].get("instruction_type"),
                    "priority": i["metadata"].get("priority"),
                    "is_active": i["metadata"].get("is_active"),
                    "applies_to": json.loads(i["metadata"].get("applies_to", "[]")),
                    "timestamp": i["metadata"].get("timestamp")
                }
                for i in self._memory_store["design_instructions"]
            ]
    
    def toggle_instruction(self, instruction_id: str, is_active: bool) -> bool:
        """Enable or disable a design instruction."""
        if CHROMADB_AVAILABLE:
            existing = self.design_instructions.get(
                ids=[instruction_id],
                include=["metadatas"]
            )
            if not existing or not existing.get("ids"):
                return False
            
            meta = existing["metadatas"][0]
            meta["is_active"] = is_active
            meta["timestamp"] = datetime.now().isoformat()
            
            self.design_instructions.update(
                ids=[instruction_id],
                metadatas=[meta]
            )
            return True
        else:
            for i in self._memory_store["design_instructions"]:
                if i["id"] == instruction_id:
                    i["metadata"]["is_active"] = is_active
                    i["metadata"]["timestamp"] = datetime.now().isoformat()
                    return True
            return False
    
    def delete_design_instruction(self, instruction_id: str) -> bool:
        """Delete a design instruction."""
        if CHROMADB_AVAILABLE:
            try:
                self.design_instructions.delete(ids=[instruction_id])
                logger.info(f"Deleted design instruction: {instruction_id}")
                return True
            except Exception:
                return False
        else:
            original_len = len(self._memory_store["design_instructions"])
            self._memory_store["design_instructions"] = [
                i for i in self._memory_store["design_instructions"] if i["id"] != instruction_id
            ]
            return len(self._memory_store["design_instructions"]) < original_len
    
    # =========================================================================
    # Search Criteria (Saved Searches)
    # =========================================================================
    
    def save_search_criteria(
        self,
        name: str,
        role: Optional[str] = None,
        location: Optional[str] = None,
        keywords: Optional[list[str]] = None,
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
        remote_preference: Optional[str] = None,  # "remote", "hybrid", "onsite", "any"
        experience_level: Optional[str] = None,  # "entry", "mid", "senior", "executive"
        company_size: Optional[str] = None,  # "startup", "small", "medium", "large", "enterprise"
        industries: Optional[list[str]] = None,
        exclude_companies: Optional[list[str]] = None,
        is_default: bool = False,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save job search criteria for reuse.
        
        Args:
            name: Friendly name for this saved search (e.g., "Remote ML Jobs SF")
            role: Target job role/title
            location: Preferred location(s)
            keywords: Required keywords/skills
            salary_min: Minimum salary
            salary_max: Maximum salary
            remote_preference: remote/hybrid/onsite/any
            experience_level: entry/mid/senior/executive
            company_size: startup/small/medium/large/enterprise
            industries: Target industries
            exclude_companies: Companies to exclude
            is_default: Whether this is the default search criteria
            metadata: Additional metadata
        
        Returns:
            ID of the saved criteria
        """
        doc_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        
        criteria = {
            "role": role,
            "location": location,
            "keywords": keywords or [],
            "salary_min": salary_min,
            "salary_max": salary_max,
            "remote_preference": remote_preference or "any",
            "experience_level": experience_level,
            "company_size": company_size,
            "industries": industries or [],
            "exclude_companies": exclude_companies or []
        }
        
        doc_metadata = {
            "name": name,
            "criteria_json": json.dumps(criteria),
            "is_default": is_default,
            "timestamp": timestamp,
            "last_used": timestamp,
            "use_count": 0,
            "type": "search_criteria"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        # Create searchable document text
        search_text_parts = [f"Saved Search: {name}"]
        if role:
            search_text_parts.append(f"Role: {role}")
        if location:
            search_text_parts.append(f"Location: {location}")
        if keywords:
            search_text_parts.append(f"Keywords: {', '.join(keywords)}")
        if remote_preference:
            search_text_parts.append(f"Remote: {remote_preference}")
        if experience_level:
            search_text_parts.append(f"Level: {experience_level}")
        if industries:
            search_text_parts.append(f"Industries: {', '.join(industries)}")
        
        combined_text = "\n".join(search_text_parts)
        
        if CHROMADB_AVAILABLE:
            # If setting as default, unset other defaults first
            if is_default:
                self._unset_default_criteria()
            
            self.search_criteria_collection.add(
                ids=[doc_id],
                documents=[combined_text],
                metadatas=[doc_metadata]
            )
        else:
            if is_default:
                for item in self._memory_store["search_criteria"]:
                    item["metadata"]["is_default"] = False
            
            self._memory_store["search_criteria"].append({
                "id": doc_id,
                "document": combined_text,
                "metadata": doc_metadata
            })
        
        logger.info(f"Saved search criteria: {name} (ID: {doc_id})")
        return doc_id
    
    def _unset_default_criteria(self):
        """Unset is_default flag on all existing criteria."""
        if CHROMADB_AVAILABLE:
            existing = self.search_criteria_collection.get(
                where={"is_default": True},
                include=["metadatas"]
            )
            if existing and existing.get("ids"):
                for i, doc_id in enumerate(existing["ids"]):
                    metadata = existing["metadatas"][i]
                    metadata["is_default"] = False
                    self.search_criteria_collection.update(
                        ids=[doc_id],
                        metadatas=[metadata]
                    )
    
    def get_search_criteria(self, criteria_id: str) -> Optional[dict]:
        """Get search criteria by ID."""
        if CHROMADB_AVAILABLE:
            results = self.search_criteria_collection.get(
                ids=[criteria_id],
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            if formatted:
                result = formatted[0]
                # Parse the criteria JSON
                criteria_json = result.get("metadata", {}).get("criteria_json", "{}")
                result["criteria"] = json.loads(criteria_json)
                return result
            return None
        else:
            for item in self._memory_store["search_criteria"]:
                if item["id"] == criteria_id:
                    result = item.copy()
                    result["criteria"] = json.loads(result["metadata"].get("criteria_json", "{}"))
                    return result
            return None
    
    def get_search_criteria_by_name(self, name: str) -> Optional[dict]:
        """Get search criteria by name."""
        if CHROMADB_AVAILABLE:
            results = self.search_criteria_collection.get(
                where={"name": name},
                limit=1,
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            if formatted:
                result = formatted[0]
                result["criteria"] = json.loads(result.get("metadata", {}).get("criteria_json", "{}"))
                return result
            return None
        else:
            for item in self._memory_store["search_criteria"]:
                if item["metadata"].get("name", "").lower() == name.lower():
                    result = item.copy()
                    result["criteria"] = json.loads(result["metadata"].get("criteria_json", "{}"))
                    return result
            return None
    
    def get_default_search_criteria(self) -> Optional[dict]:
        """Get the default search criteria if set."""
        if CHROMADB_AVAILABLE:
            results = self.search_criteria_collection.get(
                where={"is_default": True},
                limit=1,
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            if formatted:
                result = formatted[0]
                result["criteria"] = json.loads(result.get("metadata", {}).get("criteria_json", "{}"))
                return result
            return None
        else:
            for item in self._memory_store["search_criteria"]:
                if item["metadata"].get("is_default"):
                    result = item.copy()
                    result["criteria"] = json.loads(result["metadata"].get("criteria_json", "{}"))
                    return result
            return None
    
    def list_search_criteria(self, limit: int = 20) -> list[dict]:
        """List all saved search criteria."""
        if CHROMADB_AVAILABLE:
            results = self.search_criteria_collection.get(
                limit=limit,
                include=["documents", "metadatas"]
            )
            formatted = self._format_get_results(results)
            for item in formatted:
                item["criteria"] = json.loads(item.get("metadata", {}).get("criteria_json", "{}"))
            return formatted
        else:
            results = []
            for item in self._memory_store["search_criteria"][:limit]:
                result = item.copy()
                result["criteria"] = json.loads(result["metadata"].get("criteria_json", "{}"))
                results.append(result)
            return results
    
    def update_search_criteria(
        self,
        criteria_id: str,
        name: Optional[str] = None,
        role: Optional[str] = None,
        location: Optional[str] = None,
        keywords: Optional[list[str]] = None,
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
        remote_preference: Optional[str] = None,
        experience_level: Optional[str] = None,
        company_size: Optional[str] = None,
        industries: Optional[list[str]] = None,
        exclude_companies: Optional[list[str]] = None,
        is_default: Optional[bool] = None
    ) -> bool:
        """
        Update existing search criteria.
        
        Returns:
            True if updated successfully, False if not found
        """
        existing = self.get_search_criteria(criteria_id)
        if not existing:
            return False
        
        # Get current criteria and update
        current_criteria = existing.get("criteria", {})
        current_metadata = existing.get("metadata", {})
        
        # Update criteria fields if provided
        if role is not None:
            current_criteria["role"] = role
        if location is not None:
            current_criteria["location"] = location
        if keywords is not None:
            current_criteria["keywords"] = keywords
        if salary_min is not None:
            current_criteria["salary_min"] = salary_min
        if salary_max is not None:
            current_criteria["salary_max"] = salary_max
        if remote_preference is not None:
            current_criteria["remote_preference"] = remote_preference
        if experience_level is not None:
            current_criteria["experience_level"] = experience_level
        if company_size is not None:
            current_criteria["company_size"] = company_size
        if industries is not None:
            current_criteria["industries"] = industries
        if exclude_companies is not None:
            current_criteria["exclude_companies"] = exclude_companies
        
        # Update metadata
        if name is not None:
            current_metadata["name"] = name
        if is_default is not None:
            if is_default:
                self._unset_default_criteria()
            current_metadata["is_default"] = is_default
        
        current_metadata["criteria_json"] = json.dumps(current_criteria)
        current_metadata["timestamp"] = datetime.now().isoformat()
        
        # Rebuild document text
        search_text_parts = [f"Saved Search: {current_metadata.get('name', 'Unnamed')}"]
        if current_criteria.get("role"):
            search_text_parts.append(f"Role: {current_criteria['role']}")
        if current_criteria.get("location"):
            search_text_parts.append(f"Location: {current_criteria['location']}")
        if current_criteria.get("keywords"):
            search_text_parts.append(f"Keywords: {', '.join(current_criteria['keywords'])}")
        
        combined_text = "\n".join(search_text_parts)
        
        if CHROMADB_AVAILABLE:
            self.search_criteria_collection.update(
                ids=[criteria_id],
                documents=[combined_text],
                metadatas=[current_metadata]
            )
        else:
            for item in self._memory_store["search_criteria"]:
                if item["id"] == criteria_id:
                    item["document"] = combined_text
                    item["metadata"] = current_metadata
                    break
        
        logger.info(f"Updated search criteria: {criteria_id}")
        return True
    
    def delete_search_criteria(self, criteria_id: str) -> bool:
        """Delete search criteria by ID."""
        if CHROMADB_AVAILABLE:
            try:
                self.search_criteria_collection.delete(ids=[criteria_id])
                logger.info(f"Deleted search criteria: {criteria_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete search criteria: {e}")
                return False
        else:
            for i, item in enumerate(self._memory_store["search_criteria"]):
                if item["id"] == criteria_id:
                    self._memory_store["search_criteria"].pop(i)
                    logger.info(f"Deleted search criteria: {criteria_id}")
                    return True
            return False
    
    def mark_criteria_used(self, criteria_id: str) -> bool:
        """Mark search criteria as used (updates last_used and increments use_count)."""
        existing = self.get_search_criteria(criteria_id)
        if not existing:
            return False
        
        metadata = existing.get("metadata", {})
        metadata["last_used"] = datetime.now().isoformat()
        metadata["use_count"] = metadata.get("use_count", 0) + 1
        
        if CHROMADB_AVAILABLE:
            self.search_criteria_collection.update(
                ids=[criteria_id],
                metadatas=[metadata]
            )
        else:
            for item in self._memory_store["search_criteria"]:
                if item["id"] == criteria_id:
                    item["metadata"] = metadata
                    break
        
        return True
    
    def search_criteria_by_role(self, role: str, n_results: int = 5) -> list[dict]:
        """Find saved searches matching a role."""
        if CHROMADB_AVAILABLE:
            results = self.search_criteria_collection.query(
                query_texts=[role],
                n_results=n_results
            )
            formatted = self._format_results(results)
            for item in formatted:
                item["criteria"] = json.loads(item.get("metadata", {}).get("criteria_json", "{}"))
            return formatted
        else:
            return self._memory_search("search_criteria", role, n_results)
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _format_results(self, results: dict) -> list[dict]:
        """Format ChromaDB query results."""
        formatted = []
        if results and results.get("ids"):
            for i, doc_id in enumerate(results["ids"][0]):
                formatted.append({
                    "id": doc_id,
                    "document": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else None
                })
        return formatted
    
    def _format_get_results(self, results: dict) -> list[dict]:
        """Format ChromaDB get results."""
        formatted = []
        if results and results.get("ids"):
            for i, doc_id in enumerate(results["ids"]):
                formatted.append({
                    "id": doc_id,
                    "document": results["documents"][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][i] if results.get("metadatas") else {}
                })
        return formatted
    
    def _memory_search(self, collection: str, query: str, n_results: int) -> list[dict]:
        """Simple keyword search for in-memory store."""
        query_lower = query.lower()
        results = []
        for item in self._memory_store.get(collection, []):
            doc = item.get("document", "").lower()
            if query_lower in doc:
                results.append(item)
        return results[:n_results]
    
    # =========================================================================
    # Response Cache (Agent Response Caching)
    # =========================================================================
    
    def _generate_cache_key(self, cache_type: str, query: str, **params) -> str:
        """Generate a unique cache key from query and parameters."""
        key_data = f"{cache_type}:{query}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]
    
    def _is_cache_valid(self, timestamp_str: str, cache_type: str) -> bool:
        """Check if a cached item is still valid (not expired)."""
        try:
            cached_time = datetime.fromisoformat(timestamp_str)
            expiry_hours = self.CACHE_EXPIRY_HOURS.get(cache_type, self.CACHE_EXPIRY_HOURS["default"])
            return datetime.now() - cached_time < timedelta(hours=expiry_hours)
        except (ValueError, TypeError):
            return False
    
    def get_cached_response(
        self,
        cache_type: str,
        query: str,
        **params
    ) -> Optional[dict]:
        """
        Get a cached response if available and not expired.
        
        Args:
            cache_type: Type of cache (search_results, job_analysis, company_analysis, etc.)
            query: The original query/input
            **params: Additional parameters that affect the cache key
        
        Returns:
            Cached response dict or None if not found/expired
        """
        cache_key = self._generate_cache_key(cache_type, query, **params)
        
        if CHROMADB_AVAILABLE:
            try:
                results = self.response_cache.get(
                    ids=[cache_key],
                    include=["documents", "metadatas"]
                )
                if results and results.get("ids") and len(results["ids"]) > 0:
                    metadata = results["metadatas"][0] if results.get("metadatas") else {}
                    if self._is_cache_valid(metadata.get("timestamp", ""), cache_type):
                        logger.info(f"✅ Cache HIT for {cache_type}: {query[:50]}...")
                        return {
                            "cached": True,
                            "cache_key": cache_key,
                            "response": results["documents"][0],
                            "metadata": metadata,
                            "timestamp": metadata.get("timestamp"),
                            "sources": json.loads(metadata.get("sources", "[]"))
                        }
                    else:
                        logger.debug(f"Cache EXPIRED for {cache_type}: {query[:50]}...")
                        # Delete expired entry
                        self.response_cache.delete(ids=[cache_key])
            except Exception as e:
                logger.debug(f"Cache lookup failed: {e}")
        else:
            # In-memory cache lookup
            for item in self._memory_store["response_cache"]:
                if item.get("id") == cache_key:
                    metadata = item.get("metadata", {})
                    if self._is_cache_valid(metadata.get("timestamp", ""), cache_type):
                        logger.info(f"✅ Cache HIT for {cache_type}: {query[:50]}...")
                        return {
                            "cached": True,
                            "cache_key": cache_key,
                            "response": item.get("document"),
                            "metadata": metadata,
                            "timestamp": metadata.get("timestamp"),
                            "sources": json.loads(metadata.get("sources", "[]"))
                        }
        
        logger.debug(f"Cache MISS for {cache_type}: {query[:50]}...")
        return None
    
    def set_cached_response(
        self,
        cache_type: str,
        query: str,
        response: str,
        sources: Optional[list[dict]] = None,
        **params
    ) -> str:
        """
        Cache an agent response.
        
        Args:
            cache_type: Type of cache (search_results, job_analysis, company_analysis, etc.)
            query: The original query/input
            response: The response to cache
            sources: List of source dicts with url, title, platform fields
            **params: Additional parameters that affect the cache key
        
        Returns:
            Cache key
        """
        cache_key = self._generate_cache_key(cache_type, query, **params)
        timestamp = datetime.now().isoformat()
        
        metadata = {
            "cache_type": cache_type,
            "query": query[:500],  # Truncate long queries
            "timestamp": timestamp,
            "sources": json.dumps(sources or []),
            **{k: str(v)[:200] for k, v in params.items()}  # Truncate param values
        }
        
        if CHROMADB_AVAILABLE:
            # Delete existing entry if any
            try:
                self.response_cache.delete(ids=[cache_key])
            except:
                pass
            
            self.response_cache.add(
                ids=[cache_key],
                documents=[response],
                metadatas=[metadata]
            )
        else:
            # Remove existing entry
            self._memory_store["response_cache"] = [
                item for item in self._memory_store["response_cache"]
                if item.get("id") != cache_key
            ]
            self._memory_store["response_cache"].append({
                "id": cache_key,
                "document": response,
                "metadata": metadata
            })
        
        logger.info(f"📦 Cached {cache_type} response: {query[:50]}...")
        return cache_key
    
    def invalidate_cache(
        self,
        cache_type: Optional[str] = None,
        older_than_hours: Optional[int] = None
    ) -> int:
        """
        Invalidate cached responses.
        
        Args:
            cache_type: If provided, only invalidate this type. None = all.
            older_than_hours: If provided, only invalidate entries older than this.
        
        Returns:
            Number of entries invalidated
        """
        invalidated = 0
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours) if older_than_hours else None
        
        if CHROMADB_AVAILABLE:
            try:
                all_cache = self.response_cache.get(include=["metadatas"])
                ids_to_delete = []
                
                for i, cache_id in enumerate(all_cache.get("ids", [])):
                    metadata = all_cache["metadatas"][i] if all_cache.get("metadatas") else {}
                    
                    # Check cache_type filter
                    if cache_type and metadata.get("cache_type") != cache_type:
                        continue
                    
                    # Check age filter
                    if cutoff_time:
                        try:
                            cached_time = datetime.fromisoformat(metadata.get("timestamp", ""))
                            if cached_time >= cutoff_time:
                                continue
                        except:
                            pass
                    
                    ids_to_delete.append(cache_id)
                
                if ids_to_delete:
                    self.response_cache.delete(ids=ids_to_delete)
                    invalidated = len(ids_to_delete)
                    
            except Exception as e:
                logger.warning(f"Cache invalidation failed: {e}")
        else:
            original_count = len(self._memory_store["response_cache"])
            self._memory_store["response_cache"] = [
                item for item in self._memory_store["response_cache"]
                if not (
                    (not cache_type or item.get("metadata", {}).get("cache_type") == cache_type) and
                    (not cutoff_time or datetime.fromisoformat(item.get("metadata", {}).get("timestamp", datetime.now().isoformat())) < cutoff_time)
                )
            ]
            invalidated = original_count - len(self._memory_store["response_cache"])
        
        if invalidated > 0:
            logger.info(f"🗑️ Invalidated {invalidated} cache entries")
        return invalidated
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        if CHROMADB_AVAILABLE:
            try:
                all_cache = self.response_cache.get(include=["metadatas"])
                by_type = {}
                expired = 0
                
                for i, _ in enumerate(all_cache.get("ids", [])):
                    metadata = all_cache["metadatas"][i] if all_cache.get("metadatas") else {}
                    cache_type = metadata.get("cache_type", "unknown")
                    by_type[cache_type] = by_type.get(cache_type, 0) + 1
                    
                    if not self._is_cache_valid(metadata.get("timestamp", ""), cache_type):
                        expired += 1
                
                return {
                    "total_entries": self.response_cache.count(),
                    "by_type": by_type,
                    "expired": expired,
                    "storage": "chromadb"
                }
            except Exception as e:
                return {"error": str(e)}
        else:
            by_type = {}
            for item in self._memory_store["response_cache"]:
                cache_type = item.get("metadata", {}).get("cache_type", "unknown")
                by_type[cache_type] = by_type.get(cache_type, 0) + 1
            
            return {
                "total_entries": len(self._memory_store["response_cache"]),
                "by_type": by_type,
                "storage": "in-memory"
            }
    
    # =========================================================================
    # Search Results Cache (with Source Links)
    # =========================================================================
    
    def save_search_results(
        self,
        query: str,
        role: str,
        location: str,
        results: list[dict],
        platform: Optional[str] = None
    ) -> str:
        """
        Save search results with source links.
        
        Args:
            query: The search query
            role: Job role searched
            location: Location searched
            results: List of job results, each should have:
                - title: Job title
                - company: Company name
                - url: Source URL (REQUIRED)
                - platform: Where found (linkedin, indeed, glassdoor)
                - location: Job location
                - posted_date: When posted (if available)
                - salary: Salary info (if available)
            platform: Platform name if all from same source
        
        Returns:
            Cache key for these results
        """
        cache_key = self._generate_cache_key("search_results", query, role=role, location=location, platform=platform or "all")
        timestamp = datetime.now().isoformat()
        
        # Ensure each result has required fields
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title", "Unknown Title"),
                "company": r.get("company", "Unknown Company"),
                "url": r.get("url", ""),  # Source URL is critical
                "platform": r.get("platform", platform or "unknown"),
                "location": r.get("location", location),
                "posted_date": r.get("posted_date", ""),
                "salary": r.get("salary", ""),
                "description_snippet": r.get("description_snippet", "")[:500]
            })
        
        metadata = {
            "query": query,
            "role": role,
            "location": location,
            "platform": platform or "all",
            "result_count": len(formatted_results),
            "timestamp": timestamp
        }
        
        document = json.dumps({
            "query": query,
            "role": role,
            "location": location,
            "results": formatted_results,
            "timestamp": timestamp
        })
        
        if CHROMADB_AVAILABLE:
            try:
                self.search_results_cache.delete(ids=[cache_key])
            except:
                pass
            
            self.search_results_cache.add(
                ids=[cache_key],
                documents=[document],
                metadatas=[metadata]
            )
        else:
            self._memory_store["search_results_cache"] = [
                item for item in self._memory_store["search_results_cache"]
                if item.get("id") != cache_key
            ]
            self._memory_store["search_results_cache"].append({
                "id": cache_key,
                "document": document,
                "metadata": metadata
            })
        
        logger.info(f"📦 Cached {len(formatted_results)} search results for: {role} in {location}")
        return cache_key
    
    def get_cached_search_results(
        self,
        role: str,
        location: str,
        platform: Optional[str] = None,
        max_age_hours: int = 24
    ) -> Optional[dict]:
        """
        Get cached search results if available and fresh.
        
        Args:
            role: Job role to search
            location: Location to search
            platform: Specific platform or None for all
            max_age_hours: Maximum age of cached results
        
        Returns:
            Dict with results and metadata, or None if not found/expired
        """
        query = f"{role} {location}"
        cache_key = self._generate_cache_key("search_results", query, role=role, location=location, platform=platform or "all")
        
        if CHROMADB_AVAILABLE:
            try:
                results = self.search_results_cache.get(
                    ids=[cache_key],
                    include=["documents", "metadatas"]
                )
                if results and results.get("ids") and len(results["ids"]) > 0:
                    metadata = results["metadatas"][0] if results.get("metadatas") else {}
                    timestamp = metadata.get("timestamp", "")
                    
                    # Check if still valid
                    try:
                        cached_time = datetime.fromisoformat(timestamp)
                        if datetime.now() - cached_time < timedelta(hours=max_age_hours):
                            data = json.loads(results["documents"][0])
                            logger.info(f"✅ Search cache HIT: {role} in {location} ({len(data.get('results', []))} results)")
                            return {
                                "cached": True,
                                "cache_key": cache_key,
                                "timestamp": timestamp,
                                "results": data.get("results", []),
                                "metadata": metadata
                            }
                    except:
                        pass
                    
                    # Expired - delete
                    self.search_results_cache.delete(ids=[cache_key])
            except Exception as e:
                logger.debug(f"Search cache lookup failed: {e}")
        else:
            for item in self._memory_store["search_results_cache"]:
                if item.get("id") == cache_key:
                    metadata = item.get("metadata", {})
                    timestamp = metadata.get("timestamp", "")
                    try:
                        cached_time = datetime.fromisoformat(timestamp)
                        if datetime.now() - cached_time < timedelta(hours=max_age_hours):
                            data = json.loads(item.get("document", "{}"))
                            logger.info(f"✅ Search cache HIT: {role} in {location}")
                            return {
                                "cached": True,
                                "cache_key": cache_key,
                                "timestamp": timestamp,
                                "results": data.get("results", []),
                                "metadata": metadata
                            }
                    except:
                        pass
        
        logger.debug(f"Search cache MISS: {role} in {location}")
        return None
    
    def get_stats(self) -> dict:
        """Get storage statistics."""
        if CHROMADB_AVAILABLE:
            cache_stats = self.get_cache_stats()
            return {
                "job_postings": self.job_postings.count(),
                "resumes": self.resumes.count(),
                "resume_versions": self.resume_versions.count(),
                "cover_letters": self.cover_letters.count(),
                "user_profiles": self.user_profiles.count(),
                "company_analyses": self.company_analyses.count(),
                "search_sessions": self.search_sessions.count(),
                "search_criteria": self.search_criteria_collection.count(),
                "resume_templates": self.resume_templates.count(),
                "design_instructions": self.design_instructions.count(),
                "response_cache": self.response_cache.count(),
                "search_results_cache": self.search_results_cache.count(),
                "cache_stats": cache_stats,
                "storage": "chromadb",
                "path": self.persist_directory
            }
        else:
            cache_stats = self.get_cache_stats()
            return {
                "job_postings": len(self._memory_store["job_postings"]),
                "resumes": len(self._memory_store["resumes"]),
                "resume_versions": len(self._memory_store["resume_versions"]),
                "cover_letters": len(self._memory_store["cover_letters"]),
                "user_profiles": len(self._memory_store["user_profiles"]),
                "company_analyses": len(self._memory_store["company_analyses"]),
                "search_sessions": len(self._memory_store["search_sessions"]),
                "search_criteria": len(self._memory_store["search_criteria"]),
                "resume_templates": len(self._memory_store["resume_templates"]),
                "design_instructions": len(self._memory_store["design_instructions"]),
                "response_cache": len(self._memory_store["response_cache"]),
                "search_results_cache": len(self._memory_store["search_results_cache"]),
                "cache_stats": cache_stats,
                "storage": "in-memory",
                "path": None
            }


# Global instance for easy access
_vector_store: Optional[JobSearchVectorStore] = None


def get_vector_store() -> JobSearchVectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = JobSearchVectorStore()
    return _vector_store

