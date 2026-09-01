"""
Academix AI — Auth Router

Endpoints: login, signup (admin only), refresh, profile
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, require_role, CurrentUser
from app.models.user import LoginRequest, SignUpRequest, LoginResponse, UserResponse, UserUpdate
from app.services import auth_service

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    """Sign in with email + password. Returns JWT tokens + user profile."""
    try:
        result = await auth_service.sign_in_user(data)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid credentials: {str(e)}",
        )


@router.post("/signup", response_model=UserResponse)
async def signup(
    data: SignUpRequest,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """
    Create a new user account (admin only).
    The user is auto-confirmed and a profile is created via DB trigger.
    """
    try:
        result = await auth_service.sign_up_user(data)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create user: {str(e)}",
        )


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh an expired access token."""
    try:
        result = await auth_service.refresh_session(refresh_token)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}",
        )


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    profile = await auth_service.get_user_profile(current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    data: UserUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update the current user's own profile."""
    result = await auth_service.update_user_profile(
        current_user.id, data.model_dump(exclude_none=True)
    )
    return result
