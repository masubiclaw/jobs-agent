"""Document generation service wrapping existing tools."""

import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from api.models import DocumentResponse, DocumentType, QualityScores, DocumentListItem
from api.services.profile_service import ProfileService
from api.services.job_service import JobService

# Import existing tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from job_agent_coordinator.tools.toon_format import to_toon, from_toon

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Document generation service.
    
    Generates resumes and cover letters using existing tools.
    """
    
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
        return self._user_docs_dir(user_id) / "_index.toon"
    
    def _load_docs_index(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Load documents index."""
        index_file = self._docs_index_file(user_id)
        if index_file.exists():
            try:
                data = from_toon(index_file.read_text())
                return data.get("documents", {}) if isinstance(data, dict) else {}
            except:
                pass
        return {}
    
    def _save_docs_index(self, user_id: str, index: Dict[str, Dict[str, Any]]):
        """Save documents index."""
        index_file = self._docs_index_file(user_id)
        data = {
            "documents": index,
            "updated_at": datetime.now().isoformat()
        }
        index_file.write_text(to_toon(data) + '\n')
    
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
        """Generate a document (resume or cover letter)."""
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
            
            # Convert to dict for existing tools
            profile_dict = self._profile_to_dict(profile_response)
            job_dict = self._job_to_dict(job_response)
            
            # Import and use existing tools
            from job_agent_coordinator.tools.resume_tools import generate_resume, generate_cover_letter
            
            if document_type == DocumentType.RESUME:
                result = generate_resume(job_id, profile_response.id)
            else:
                result = generate_cover_letter(job_id, profile_response.id)
            
            if not result or not isinstance(result, dict):
                logger.error(f"Document generation failed: {result}")
                return None
            
            # Parse result
            doc_id = self._generate_doc_id(job_id, profile_response.id, document_type)
            
            quality_scores = QualityScores(
                fact_score=result.get("fact_score", 0),
                keyword_score=result.get("keyword_score", 0),
                ats_score=result.get("ats_score", 0),
                length_score=result.get("length_score", 0),
                overall_score=result.get("overall_score", 0)
            )
            
            response = DocumentResponse(
                id=doc_id,
                job_id=job_id,
                profile_id=profile_response.id,
                document_type=document_type,
                content=result.get("content", ""),
                pdf_path=result.get("pdf_path"),
                quality_scores=quality_scores,
                iterations=result.get("iterations", 1),
                created_at=datetime.now()
            )
            
            # Save to index
            index = self._load_docs_index(user_id)
            index[doc_id] = {
                "id": doc_id,
                "job_id": job_id,
                "profile_id": profile_response.id,
                "document_type": document_type.value,
                "pdf_path": result.get("pdf_path"),
                "overall_score": quality_scores.overall_score,
                "job_title": job_response.title,
                "job_company": job_response.company,
                "job_url": job_response.url or None,
                "reviewed": False,
                "is_good": None,
                "created_at": datetime.now().isoformat()
            }
            self._save_docs_index(user_id, index)
            
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
        """Get PDF path for a document."""
        index = self._load_docs_index(user_id)
        doc_info = index.get(document_id)
        
        if not doc_info or not doc_info.get("pdf_path"):
            return None
        
        pdf_path = Path(doc_info["pdf_path"])
        if pdf_path.exists():
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
            "skills": [{"name": s.name, "level": s.level.value if hasattr(s.level, 'value') else s.level} for s in profile.skills],
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
        """Update reviewed/is_good flags on a document."""
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
