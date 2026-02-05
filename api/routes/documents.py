"""Document generation routes."""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse

from api.models import DocumentRequest, DocumentResponse, DocumentType, UserResponse
from api.auth import get_current_user
from api.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_document_service() -> DocumentService:
    """Dependency to get document service."""
    return DocumentService()


@router.post("/resume", response_model=DocumentResponse)
async def generate_resume(
    request: DocumentRequest,
    current_user: UserResponse = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Generate a tailored resume for a specific job."""
    request.document_type = DocumentType.RESUME
    
    result = service.generate_document(
        user_id=current_user.id,
        job_id=request.job_id,
        profile_id=request.profile_id,
        document_type=DocumentType.RESUME
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to generate resume. Check that job and profile exist."
        )
    
    return result


@router.post("/cover-letter", response_model=DocumentResponse)
async def generate_cover_letter(
    request: DocumentRequest,
    current_user: UserResponse = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """Generate a tailored cover letter for a specific job."""
    result = service.generate_document(
        user_id=current_user.id,
        job_id=request.job_id,
        profile_id=request.profile_id,
        document_type=DocumentType.COVER_LETTER
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to generate cover letter. Check that job and profile exist."
        )
    
    return result


@router.post("/package", response_model=dict)
async def generate_application_package(
    request: DocumentRequest,
    current_user: UserResponse = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
) -> dict:
    """Generate both resume and cover letter for a specific job."""
    result = service.generate_package(
        user_id=current_user.id,
        job_id=request.job_id,
        profile_id=request.profile_id
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to generate application package."
        )
    
    return result


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: UserResponse = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service)
):
    """Download a generated document as PDF."""
    pdf_path = service.get_document_pdf(document_id, current_user.id)
    
    if not pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name if hasattr(pdf_path, 'name') else "document.pdf"
    )
