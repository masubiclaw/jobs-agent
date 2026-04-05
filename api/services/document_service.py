"""Document generation service wrapping existing tools."""

import logging
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from api.models import DocumentResponse, DocumentType, QualityScores, DocumentListItem
from api.services.profile_service import ProfileService
from api.services.job_service import JobService

# Import existing tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import json
from job_agent_coordinator.tools.resume_tools import (
    _run_section_generation_loop, _run_generation_loop
)
from job_agent_coordinator.tools.pdf_generator import (
    generate_resume_pdf, generate_cover_letter_pdf, validate_single_page
)
from job_agent_coordinator.tools.document_generator import generate_resume_content
from job_agent_coordinator.tools.document_critic import critique_document

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Document generation service.

    Generates resumes and cover letters using existing tools.
    """

    # Class-level dict of locks per user_id for index read-modify-write
    _user_locks: Dict[str, threading.Lock] = {}
    _user_locks_lock = threading.Lock()

    @classmethod
    def _get_user_lock(cls, user_id: str) -> threading.Lock:
        """Get or create a lock for a specific user_id."""
        with cls._user_locks_lock:
            if user_id not in cls._user_locks:
                cls._user_locks[user_id] = threading.Lock()
            return cls._user_locks[user_id]

    def __init__(self, base_dir: Path = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".job_cache/users")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._profile_service = ProfileService()
        self._job_service = JobService()
    
    def _user_docs_dir(self, user_id: str) -> Path:
        """Get documents directory for a user."""
        docs_dir = self.base_dir / user_id / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        return docs_dir
    
    def _docs_index_file(self, user_id: str) -> Path:
        """Get documents index file."""
        return self._user_docs_dir(user_id) / "_index.json"

    def _load_docs_index(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Load documents index."""
        index_file = self._docs_index_file(user_id)
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text())
                return data.get("documents", {}) if isinstance(data, dict) else {}
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"Failed to load docs index for user: {e}")
                return {}
        return {}

    def _save_docs_index(self, user_id: str, index: Dict[str, Dict[str, Any]]):
        """Save documents index."""
        index_file = self._docs_index_file(user_id)
        data = {
            "documents": index,
            "updated_at": datetime.now().isoformat()
        }
        index_file.write_text(json.dumps(data, indent=2))

    def _update_docs_index(self, user_id: str, doc_id: str, doc_info: Dict[str, Any]):
        """Thread-safe update of a single entry in the docs index."""
        lock = self._get_user_lock(user_id)
        with lock:
            index = self._load_docs_index(user_id)
            index[doc_id] = doc_info
            self._save_docs_index(user_id, index)
    
    def _generate_doc_id(self, job_id: str, profile_id: str, doc_type: DocumentType) -> str:
        """Generate unique document ID."""
        content = f"{job_id}:{profile_id}:{doc_type.value}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def generate_document(
        self,
        user_id: str,
        job_id: str,
        profile_id: Optional[str],
        document_type: DocumentType
    ) -> Optional[DocumentResponse]:
        """Generate a document (resume or cover letter).

        Calls lower-level generation functions directly with profile/job dicts,
        bypassing the TOON-returning wrapper functions in resume_tools.py
        which depend on the old single-user ProfileStore.
        """
        try:
            # Get profile
            if profile_id:
                profile_response = self._profile_service.get_profile(profile_id, user_id)
            else:
                profile_response = self._profile_service.get_active_profile(user_id)

            if not profile_response:
                logger.error("No profile found")
                return None

            # Get job
            job_response = self._job_service.get_job(job_id, user_id)
            if not job_response:
                logger.error(f"Job not found: {job_id}")
                return None

            # Convert to dict for generation tools
            profile_dict = self._profile_to_dict(profile_response)
            job_dict = self._job_to_dict(job_response)

            company = job_dict.get("company", "Unknown")
            candidate_name = profile_dict.get("name", "Candidate")
            pdf_path = None

            if document_type == DocumentType.RESUME:
                # Section-based generation with critique loop
                content, section_critiques, critique = _run_section_generation_loop(
                    profile_dict, job_dict
                )

                # Generate PDF and enforce 1-page limit (up to 2 retries)
                pdf_path = generate_resume_pdf(content, company, candidate_name)
                for attempt in range(2):
                    is_single_page, page_count, _ = validate_single_page(pdf_path)
                    if is_single_page:
                        break
                    logger.info(f"Resume is {page_count} pages, retrying (attempt {attempt + 1})")
                    page_feedback = (
                        f"CRITICAL: The resume is {page_count} pages but MUST be exactly 1 page. "
                        f"REDUCE content: shorter bullets, fewer items per role, remove least relevant details."
                    )
                    gen_result = generate_resume_content(profile_dict, job_dict, feedback=page_feedback)
                    content = gen_result["content"]
                    critique = critique_document(content, "resume", profile_dict, job_dict)
                    pdf_path = generate_resume_pdf(content, company, candidate_name)

                # Final page count for quality score
                _, final_pages, _ = validate_single_page(pdf_path)
                page_ok = (final_pages == 1)

            else:
                # Cover letter generation
                content, critique = _run_generation_loop("cover_letter", profile_dict, job_dict)

                contact_parts = []
                if profile_dict.get("email"):
                    contact_parts.append(profile_dict["email"])
                if profile_dict.get("phone"):
                    contact_parts.append(profile_dict["phone"])
                contact_info = "  |  ".join(contact_parts) if contact_parts else ""

                # Generate PDF and enforce 1-page limit (up to 2 retries)
                pdf_path = generate_cover_letter_pdf(
                    content, company, candidate_name, contact_info=contact_info
                )
                for attempt in range(2):
                    is_single_page, page_count, _ = validate_single_page(pdf_path)
                    if is_single_page:
                        break
                    logger.info(f"Cover letter is {page_count} pages, retrying (attempt {attempt + 1})")
                    from job_agent_coordinator.tools.document_generator import generate_cover_letter_content
                    page_feedback = (
                        f"CRITICAL: The cover letter is {page_count} pages but MUST be exactly 1 page. "
                        f"REDUCE to 250-300 words. Be more concise."
                    )
                    gen_result = generate_cover_letter_content(profile_dict, job_dict, feedback=page_feedback)
                    content = gen_result["content"]
                    critique = critique_document(content, "cover_letter", profile_dict, job_dict)
                    pdf_path = generate_cover_letter_pdf(
                        content, company, candidate_name, contact_info=contact_info
                    )

                # Final page count for quality score
                _, final_pages, _ = validate_single_page(pdf_path)
                page_ok = (final_pages == 1)

            # Add invisible white-text LLM footer (after critique, after page validation)
            from job_agent_coordinator.tools.pdf_generator import _add_white_text_footer
            if pdf_path:
                _add_white_text_footer(pdf_path)

            # Build response from critique object
            doc_id = self._generate_doc_id(job_id, profile_response.id, document_type)

            quality_scores = QualityScores(
                fact_score=critique.fact_score,
                keyword_score=critique.keyword_score,
                ats_score=critique.ats_score,
                length_score=100 if (critique.length_compliant and page_ok) else 50,
                overall_score=critique.overall_score if page_ok else max(critique.overall_score - 20, 0)
            )

            response = DocumentResponse(
                id=doc_id,
                job_id=job_id,
                profile_id=profile_response.id,
                document_type=document_type,
                content=content,
                pdf_path=str(pdf_path) if pdf_path else None,
                quality_scores=quality_scores,
                iterations=1,
                created_at=datetime.now()
            )

            # Save to index (thread-safe)
            self._update_docs_index(user_id, doc_id, {
                "id": doc_id,
                "job_id": job_id,
                "profile_id": profile_response.id,
                "document_type": document_type.value,
                "pdf_path": str(pdf_path) if pdf_path else None,
                "overall_score": quality_scores.overall_score,
                "job_title": job_response.title,
                "job_company": job_response.company,
                "job_url": job_response.url or None,
                "reviewed": False,
                "is_good": None,
                "created_at": datetime.now().isoformat()
            })

            return response

        except Exception as e:
            logger.error(f"Document generation error: {e}", exc_info=True)
            return None
    
    def generate_package(
        self,
        user_id: str,
        job_id: str,
        profile_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Generate both resume and cover letter."""
        resume = self.generate_document(user_id, job_id, profile_id, DocumentType.RESUME)
        cover_letter = self.generate_document(user_id, job_id, profile_id, DocumentType.COVER_LETTER)
        
        if not resume and not cover_letter:
            return None
        
        return {
            "resume": resume.model_dump() if resume else None,
            "cover_letter": cover_letter.model_dump() if cover_letter else None
        }
    
    def get_document_pdf(self, document_id: str, user_id: str) -> Optional[Path]:
        """Get PDF path for a document with path traversal protection."""
        index = self._load_docs_index(user_id)
        doc_info = index.get(document_id)

        if not doc_info or not doc_info.get("pdf_path"):
            return None

        pdf_path = Path(doc_info["pdf_path"]).resolve()

        # Validate path is within allowed directories
        allowed_dirs = [Path(".job_cache").resolve(), Path("/tmp").resolve(), Path("generated_documents").resolve()]
        if not any(pdf_path.is_relative_to(d) for d in allowed_dirs):
            logger.warning(f"Path traversal attempt blocked: {pdf_path}")
            return None

        if pdf_path.exists() and pdf_path.suffix == ".pdf":
            return pdf_path

        return None
    
    def _profile_to_dict(self, profile) -> Dict[str, Any]:
        """Convert profile response to dict for existing tools."""
        return {
            "id": profile.id,
            "name": profile.name,
            "email": profile.email,
            "phone": profile.phone,
            "location": profile.location,
            "skills": [{"name": s.name, "level": getattr(s.level, 'value', None) or getattr(s, 'level', 'intermediate') or 'intermediate'} for s in profile.skills],
            "experience": [
                {
                    "title": e.title,
                    "company": e.company,
                    "start_date": e.start_date,
                    "end_date": e.end_date,
                    "description": e.description
                }
                for e in profile.experience
            ],
            "preferences": {
                "target_roles": profile.preferences.target_roles,
                "excluded_companies": profile.preferences.excluded_companies
            },
            "resume": {
                "summary": profile.resume.summary,
                "content": profile.resume.content
            },
            "notes": profile.notes
        }
    
    def list_documents(self, user_id: str, limit: int = 100) -> List[DocumentListItem]:
        """List all generated documents for a user."""
        index = self._load_docs_index(user_id)
        items = []
        for doc_id, doc in index.items():
            items.append(DocumentListItem(
                id=doc.get("id", doc_id),
                job_id=doc.get("job_id", ""),
                profile_id=doc.get("profile_id", ""),
                document_type=doc.get("document_type", "resume"),
                job_title=doc.get("job_title", ""),
                job_company=doc.get("job_company", ""),
                job_url=doc.get("job_url"),
                overall_score=doc.get("overall_score", 0),
                reviewed=doc.get("reviewed", False),
                is_good=doc.get("is_good"),
                pdf_path=doc.get("pdf_path"),
                created_at=doc.get("created_at", ""),
            ))
        # Sort by created_at desc
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[:limit]

    def update_document_review(
        self, user_id: str, doc_id: str, reviewed: Optional[bool] = None, is_good: Optional[bool] = None
    ) -> bool:
        """Update reviewed/is_good flags on a document (thread-safe)."""
        lock = self._get_user_lock(user_id)
        with lock:
            index = self._load_docs_index(user_id)
            if doc_id not in index:
                return False
            if reviewed is not None:
                index[doc_id]["reviewed"] = reviewed
            if is_good is not None:
                index[doc_id]["is_good"] = is_good
            self._save_docs_index(user_id, index)
            return True

    def _job_to_dict(self, job) -> Dict[str, Any]:
        """Convert job response to dict for existing tools."""
        return {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary,
            "url": job.url,
            "description": job.description,
            "platform": job.platform
        }
