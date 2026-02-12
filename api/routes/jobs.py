"""Job management routes."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File

from api.models import (
    JobCreate, JobUpdate, JobResponse, JobListResponse, JobStatus,
    UserResponse
)
from api.auth import get_current_user
from api.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def get_job_service() -> JobService:
    """Dependency to get job service."""
    return JobService()


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[JobStatus] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    query: Optional[str] = None,
    semantic: bool = False,
    current_user: UserResponse = Depends(get_current_user),
    service: JobService = Depends(get_job_service)
) -> JobListResponse:
    """
    List jobs with optional filters.
    
    - **page**: Page number (1-indexed)
    - **page_size**: Number of jobs per page
    - **status**: Filter by job status (active, completed, archived)
    - **company**: Filter by company name
    - **location**: Filter by location
    - **query**: Search in title and description
    - **semantic**: Use AI-powered semantic search
    """
    return service.list_jobs(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        company=company,
        location=location,
        query=query,
        semantic=semantic
    )


@router.get("/top", response_model=List[JobResponse])
async def get_top_jobs(
    limit: int = Query(10, ge=1, le=50),
    min_score: int = Query(0, ge=0, le=100),
    current_user: UserResponse = Depends(get_current_user),
    service: JobService = Depends(get_job_service)
) -> List[JobResponse]:
    """Get top matched jobs sorted by match score."""
    return service.get_top_matches(
        user_id=current_user.id,
        limit=limit,
        min_score=min_score
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    current_user: UserResponse = Depends(get_current_user),
    service: JobService = Depends(get_job_service)
) -> JobResponse:
    """
    Add a new job.
    
    Provide either:
    - **plaintext**: Raw job description text to be parsed by LLM
    - **job_url**: URL to fetch job details from
    - Or individual fields (title, company, etc.)
    """
    job = service.create_job(
        user_id=current_user.id,
        job_data=job_data
    )
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create job. Please provide valid job details or URL."
        )
    
    return job


@router.post("/upload", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def upload_job_pdf(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    service: JobService = Depends(get_job_service)
) -> JobResponse:
    """Upload a job description PDF."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 10MB."
        )
    job = service.create_job_from_pdf(
        user_id=current_user.id,
        pdf_content=contents,
        filename=file.filename
    )
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse job from PDF"
        )
    
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: UserResponse = Depends(get_current_user),
    service: JobService = Depends(get_job_service)
) -> JobResponse:
    """Get a specific job by ID."""
    job = service.get_job(job_id, current_user.id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_data: JobUpdate,
    current_user: UserResponse = Depends(get_current_user),
    service: JobService = Depends(get_job_service)
) -> JobResponse:
    """Update a job (e.g., mark as completed)."""
    job = service.update_job(
        job_id=job_id,
        user_id=current_user.id,
        **job_data.model_dump(exclude_unset=True)
    )
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    current_user: UserResponse = Depends(get_current_user),
    service: JobService = Depends(get_job_service)
):
    """Delete a job."""
    success = service.delete_job(job_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
