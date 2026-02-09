"""Pydantic models for API request/response schemas."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---- Auth ----

class UserCreate(BaseModel):
    """Request body for user registration."""
    email: str
    password: str
    name: str


class UserLogin(BaseModel):
    """Request body for login."""
    email: str
    password: str


class UserResponse(BaseModel):
    """Authenticated user info (no password)."""
    id: str
    email: str
    name: str
    is_admin: bool = False
    created_at: datetime


class Token(BaseModel):
    """JWT access token response."""
    access_token: str


# ---- Documents ----

class DocumentType(str, Enum):
    RESUME = "resume"
    COVER_LETTER = "cover_letter"


class DocumentRequest(BaseModel):
    """Request for document generation."""
    job_id: str
    profile_id: Optional[str] = None
    document_type: Optional[DocumentType] = None  # set in route


class QualityScores(BaseModel):
    """Quality scores for a generated document."""
    fact_score: float = 0
    keyword_score: float = 0
    ats_score: float = 0
    length_score: float = 0
    overall_score: float = 0


class DocumentResponse(BaseModel):
    """Generated document metadata and content."""
    id: str
    job_id: str
    profile_id: str
    document_type: DocumentType
    content: str = ""
    pdf_path: Optional[str] = None
    quality_scores: Optional[QualityScores] = None
    iterations: int = 1
    created_at: datetime


# ---- Jobs ----

class JobStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class JobAddMethod(str, Enum):
    SCRAPED = "scraped"
    MANUAL = "manual"
    URL = "url"
    PDF = "pdf"


class MatchResult(BaseModel):
    """Match scoring result for a job."""
    keyword_score: float = 0
    llm_score: Optional[float] = None
    combined_score: float = 0
    match_level: str = "unknown"
    toon_report: str = ""
    cached_at: Optional[datetime] = None


class JobCreate(BaseModel):
    """Request to add a job (one of: job_url, plaintext, or title+company)."""
    job_url: Optional[str] = None
    plaintext: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    salary: Optional[str] = None


class JobUpdate(BaseModel):
    """Request to update job metadata."""
    status: Optional[JobStatus] = None
    notes: Optional[str] = None


class JobResponse(BaseModel):
    """Job with user-specific metadata."""
    id: str
    title: str
    company: str
    location: str
    salary: str
    url: str
    description: str
    platform: str = "unknown"
    posted_date: str = ""
    cached_at: datetime
    status: JobStatus = JobStatus.ACTIVE
    added_by: JobAddMethod = JobAddMethod.SCRAPED
    notes: str = ""
    match: Optional[MatchResult] = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ---- Profiles ----

class Skill(BaseModel):
    """A skill on a profile."""
    name: str = ""
    level: str = "intermediate"
    added_at: Optional[datetime] = None


class Experience(BaseModel):
    """Work experience entry."""
    title: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = "present"
    description: str = ""
    added_at: Optional[datetime] = None


class Preferences(BaseModel):
    """Job preferences."""
    target_roles: List[str] = Field(default_factory=list)
    target_locations: List[str] = Field(default_factory=list)
    remote_preference: str = "hybrid"
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    job_types: List[str] = Field(default_factory=lambda: ["full-time"])
    industries: List[str] = Field(default_factory=list)
    excluded_companies: List[str] = Field(default_factory=list)


class Resume(BaseModel):
    """Resume content on a profile."""
    summary: str = ""
    content: str = ""
    last_updated: Optional[datetime] = None


class ProfileCreate(BaseModel):
    """Request to create a profile."""
    name: str
    email: str = ""
    phone: str = ""
    location: str = ""


class ProfileUpdate(BaseModel):
    """Request to update a profile (all optional)."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class ProfileListItem(BaseModel):
    """Summary of a profile for listing."""
    id: str
    name: str
    location: str = ""
    skills_count: int = 0
    is_active: bool = False


class ProfileResponse(BaseModel):
    """Full profile with skills, experience, preferences, resume."""
    id: str
    name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    created_at: datetime
    updated_at: datetime
    skills: List[Skill] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)
    resume: Resume = Field(default_factory=Resume)
    notes: str = ""
    is_active: bool = False
