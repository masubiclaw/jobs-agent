"""Profile management routes."""

from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends

from api.models import (
    ProfileCreate, ProfileUpdate, ProfileResponse, ProfileListItem,
    UserResponse
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
