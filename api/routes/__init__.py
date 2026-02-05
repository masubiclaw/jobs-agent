"""API routes for the Jobs Agent."""

from .auth import router as auth_router
from .profiles import router as profiles_router
from .jobs import router as jobs_router
from .documents import router as documents_router
from .admin import router as admin_router

__all__ = [
    "auth_router",
    "profiles_router", 
    "jobs_router",
    "documents_router",
    "admin_router",
]
