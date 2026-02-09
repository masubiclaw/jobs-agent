"""Pydantic models for the Jobs Agent API."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ── Auth Models ──────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str
    name: str = ""


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_admin: bool = False
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Profile Models ───────────────────────────────────────────

class Skill(BaseModel):
    name: str
    level: str = "intermediate"
    added_at: Optional[datetime] = None


class Experience(BaseModel):
    title: str
    company: str
    start_date: str = ""
    end_date: str = "present"
    description: str = ""
    added_at: Optional[datetime] = None


class Preferences(BaseModel):
    target_roles: List[str] = []
    target_locations: List[str] = []
    remote_preference: str = "hybrid"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    job_types: List[str] = ["full-time"]
    industries: List[str] = []
    excluded_companies: List[str] = []


class Resume(BaseModel):
    summary: str = ""
    content: str = ""
    last_updated: Optional[datetime] = None


class ProfileCreate(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    location: str = ""


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[List[Skill]] = None
    experience: Optional[List[Experience]] = None
    preferences: Optional[Preferences] = None
    resume: Optional[Resume] = None
    notes: Optional[str] = None


class ProfileListItem(BaseModel):
    id: str
    name: str
    location: str = ""
    skills_count: int = 0
    is_active: bool = False


class ProfileResponse(BaseModel):
    id: str
    name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    created_at: datetime
    updated_at: datetime
    skills: List[Skill] = []
    experience: List[Experience] = []
    preferences: Preferences = Preferences()
    resume: Resume = Resume()
    notes: str = ""
    is_active: bool = False


# ── Job Models ───────────────────────────────────────────────

class JobStatus(str, Enum):
    ACTIVE = "active"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class JobAddMethod(str, Enum):
    SCRAPED = "scraped"
    MANUAL = "manual"
    URL = "url"
    PDF = "pdf"
    SEARCH = "search"


class MatchResult(BaseModel):
    keyword_score: int = 0
    llm_score: Optional[int] = None
    combined_score: int = 0
    match_level: str = "unknown"
    toon_report: str = ""
    cached_at: Optional[datetime] = None


class JobCreate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    plaintext: Optional[str] = None
    job_url: Optional[str] = None


class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    notes: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    title: str
    company: str
    location: str = ""
    salary: str = ""
    url: str = ""
    description: str = ""
    platform: str = "unknown"
    posted_date: str = ""
    cached_at: Optional[datetime] = None
    status: JobStatus = JobStatus.ACTIVE
    added_by: JobAddMethod = JobAddMethod.SCRAPED
    notes: str = ""
    match: Optional[MatchResult] = None


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Document Models ──────────────────────────────────────────

class DocumentType(str, Enum):
    RESUME = "resume"
    COVER_LETTER = "cover_letter"


class QualityScores(BaseModel):
    fact_score: float = 0
    keyword_score: float = 0
    ats_score: float = 0
    length_score: float = 0
    overall_score: float = 0


class DocumentRequest(BaseModel):
    job_id: str
    profile_id: Optional[str] = None
    document_type: Optional[DocumentType] = None


class DocumentResponse(BaseModel):
    id: str
    job_id: str
    profile_id: str
    document_type: DocumentType
    content: str = ""
    pdf_path: Optional[str] = None
    quality_scores: Optional[QualityScores] = None
    iterations: int = 1
    created_at: datetime
