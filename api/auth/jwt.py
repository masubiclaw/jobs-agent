"""JWT token handling for authentication."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from api.models import UserResponse

# Configuration - require environment variable for security
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    _env = os.getenv("ENVIRONMENT", "development").lower()
    if _env in ("production", "prod", "staging"):
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is required in production. "
            "Set it to a strong random secret."
        )
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY not set. Using insecure dev key. "
        "Set JWT_SECRET_KEY before deploying to production.",
        UserWarning
    )
    SECRET_KEY = "dev-only-insecure-key-change-in-production"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# HTTP Bearer scheme for token extraction
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.
    
    Args:
        data: Payload data to encode (should include 'sub' for user ID)
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload dict if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        # Token has expired
        return None
    except JWTError:
        # All other JWT errors (invalid signature, malformed token, etc.)
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserResponse:
    """FastAPI dependency to get the current authenticated user.
    
    Args:
        credentials: HTTP Bearer credentials from request header
        
    Returns:
        UserResponse object for the authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Import here to avoid circular dependency
    from api.auth.user_store import get_user_store
    
    user_store = get_user_store()
    user = user_store.get_by_id(user_id)
    
    if user is None:
        raise credentials_exception
    
    try:
        created_at = datetime.fromisoformat(user["created_at"])
    except (ValueError, KeyError):
        created_at = datetime.now(timezone.utc)
    
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        is_admin=user.get("is_admin", False),
        created_at=created_at,
    )


async def get_current_admin_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """FastAPI dependency to get the current user and verify admin status.
    
    Args:
        current_user: Current authenticated user from get_current_user
        
    Returns:
        UserResponse object for the authenticated admin user
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
