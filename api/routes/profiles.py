"""Profile management routes."""

from datetime import datetime
from typing import List
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File

from api.models import (
    ProfileCreate, ProfileUpdate, ProfileResponse, ProfileListItem,
    UserResponse, LinkedInImportRequest,
)
from api.auth import get_current_user
from api.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["Profiles"])


def get_profile_service() -> ProfileService:
    """Dependency to get profile service."""
    return ProfileService()


@router.get("", response_model=List[ProfileListItem])
async def list_profiles(
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> List[ProfileListItem]:
    """List all profiles for the current user."""
    profiles = service.list_profiles(current_user.id)
    return profiles


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile_data: ProfileCreate,
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    """Create a new profile."""
    profile = service.create_profile(
        user_id=current_user.id,
        name=profile_data.name,
        email=profile_data.email,
        phone=profile_data.phone,
        location=profile_data.location
    )
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile"
        )
    
    return profile


@router.post("/import/pdf", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def import_profile_from_pdf(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    """Import a profile from a PDF resume."""
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted"
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file"
        )

    # Enforce 10MB upload limit
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 10MB."
        )

    profile = service.import_from_pdf(current_user.id, contents)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse resume. Ensure the PDF contains readable text and Ollama is running."
        )

    return profile


@router.post("/import/text", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def import_profile_from_text(
    request: dict,
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    """Import a profile from plain text resume content."""
    text = request.get("text", "").strip()
    if not text or len(text) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least 50 characters of resume text."
        )

    if len(text) > 50000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text too long. Maximum 50,000 characters."
        )

    profile = service.import_from_text(current_user.id, text)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse resume text. Make sure Ollama is running."
        )

    return profile


@router.post("/import/linkedin", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def import_profile_from_linkedin(
    request: LinkedInImportRequest,
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    """Import a profile from a LinkedIn profile URL."""
    parsed = urlparse(request.url)
    if parsed.scheme not in ("https", "http") or not parsed.netloc.endswith("linkedin.com") or "/in/" not in parsed.path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid LinkedIn profile URL (e.g., https://linkedin.com/in/username)"
        )

    profile = service.import_from_linkedin(current_user.id, request.url)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to import LinkedIn profile. LinkedIn may be blocking access. Try downloading your profile as PDF instead (LinkedIn > More > Save to PDF)."
        )

    return profile


@router.get("/active", response_model=ProfileResponse)
async def get_active_profile(
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    """Get the active profile for the current user."""
    profile = service.get_active_profile(current_user.id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active profile found"
        )

    return profile


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: str,
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    """Get a specific profile."""
    profile = service.get_profile(profile_id, current_user.id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    return profile


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: str,
    profile_data: ProfileUpdate,
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    """Update a profile."""
    profile = service.update_profile(
        profile_id=profile_id,
        user_id=current_user.id,
        **profile_data.model_dump(exclude_unset=True)
    )
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: str,
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
):
    """Delete a profile."""
    success = service.delete_profile(profile_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )


@router.post("/{profile_id}/activate", response_model=ProfileResponse)
async def activate_profile(
    profile_id: str,
    current_user: UserResponse = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    """Set a profile as the active profile."""
    profile = service.set_active_profile(profile_id, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    return profile
