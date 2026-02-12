"""Authentication routes for user registration and login."""

from fastapi import APIRouter, HTTPException, status, Depends

from api.models import UserCreate, UserLogin, UserResponse, Token, PasswordChange
from api.auth import create_access_token, get_user_store, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate) -> UserResponse:
    """
    Register a new user.
    
    The first registered user automatically becomes an admin.
    """
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
async def login(credentials: UserLogin) -> Token:
    """
    Authenticate user and return JWT token.
    """
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


# /auth/me endpoint is implemented in main.py with proper Depends(get_current_user)
