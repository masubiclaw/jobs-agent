"""Authentication routes for user registration and login."""

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)
from fastapi import APIRouter, HTTPException, status, Depends, Request

from api.models import UserCreate, UserLogin, UserResponse, Token, PasswordChange
from api.auth import create_access_token, get_user_store, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Simple in-memory rate limiter: {ip: [timestamps]}
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 15  # max attempts per window


def _check_rate_limit(request: Request):
    """Check rate limit for auth endpoints. Raises 429 if exceeded."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if now - t < _RATE_LIMIT_WINDOW
    ]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again in a minute."
        )
    _rate_limit_store[client_ip].append(now)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, request: Request) -> UserResponse:
    """
    Register a new user.

    The first registered user automatically becomes an admin.
    """
    _check_rate_limit(request)
    user_store = get_user_store()

    # Check if email already exists
    existing = user_store.get_by_email(user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = user_store.create(
        email=user_data.email,
        password=user_data.password,
        name=user_data.name
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

    from datetime import datetime
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        is_admin=user.get("is_admin", False),
        created_at=datetime.fromisoformat(user["created_at"])
    )


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, request: Request) -> Token:
    """
    Authenticate user and return JWT token.
    """
    _check_rate_limit(request)
    user_store = get_user_store()

    user = user_store.authenticate(credentials.email, credentials.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": user["id"], "email": user["email"], "is_admin": user.get("is_admin", False)}
    )

    from api.auth.jwt import ACCESS_TOKEN_EXPIRE_HOURS
    return Token(access_token=access_token, expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600)



@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    data: PasswordChange,
    current_user: UserResponse = Depends(get_current_user),
) -> dict:
    """Change the current user's password."""
    user_store = get_user_store()

    # Verify current password
    authed = user_store.authenticate(current_user.email, data.current_password)
    if not authed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    user_store.update(current_user.id, password=data.new_password)
    return {"status": "ok", "message": "Password changed successfully"}


@router.post("/auto-login", response_model=Token)
async def auto_login() -> Token:
    """
    Auto-login as the default admin user.
    Creates the admin if it doesn't exist yet, then returns a JWT token.
    Only available in non-production environments.
    """
    import os
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auto-login is disabled in production"
        )
    logger.warning("Auto-login endpoint used — this should only be available in development")

    from api.main import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_NAME

    user_store = get_user_store()
    user = user_store.authenticate(DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)

    if not user:
        # Admin doesn't exist yet — create it
        user = user_store.create(
            email=DEFAULT_ADMIN_EMAIL,
            password=DEFAULT_ADMIN_PASSWORD,
            name=DEFAULT_ADMIN_NAME,
        )
        if not user:
            # Already exists but password may differ — look up by email
            user = user_store.get_by_email(DEFAULT_ADMIN_EMAIL)
        if not user:
            raise HTTPException(status_code=500, detail="Could not create or find default admin")

    # Ensure admin flag is always set for the default admin
    if not user.get("is_admin"):
        user_store.set_admin(user["id"], True)
        user["is_admin"] = True

    access_token = create_access_token(
        data={"sub": user["id"], "email": user["email"], "is_admin": user.get("is_admin", True)}
    )
    from api.auth.jwt import ACCESS_TOKEN_EXPIRE_HOURS
    return Token(access_token=access_token, expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600)


# /auth/me endpoint is implemented in main.py with proper Depends(get_current_user)
