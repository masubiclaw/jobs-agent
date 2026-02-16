"""
Jobs Agent API - FastAPI Backend

A RESTful API for the job resume builder application.
Provides endpoints for authentication, profile management, job management,
document generation, and admin operations.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.routes import auth_router, profiles_router, jobs_router, documents_router, admin_router
from api.auth import get_current_user
from api.models import UserResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Jobs Agent API...")
    yield
    logger.info("Shutting down Jobs Agent API...")


# Create FastAPI application
app = FastAPI(
    title="Jobs Agent API",
    description="API for the job resume builder application",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Health check endpoint
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "jobs-agent-api"}


# Authenticated current user endpoint (proper implementation)
@app.get("/api/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current authenticated user's information."""
    return current_user


# Include routers with /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(profiles_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Jobs Agent API",
        "version": "0.1.0",
        "docs": "/api/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
