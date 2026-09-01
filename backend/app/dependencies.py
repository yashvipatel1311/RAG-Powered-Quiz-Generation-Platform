"""
Academix AI — Authentication Dependencies

Provides FastAPI dependencies for JWT validation and role-based access control.
These are injected into route handlers via Depends().
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from typing import Optional
from pydantic import BaseModel

from app.config import get_settings
from app.database import get_supabase_admin


# Security scheme — extracts Bearer token from Authorization header
security = HTTPBearer()


class CurrentUser(BaseModel):
    """Represents the authenticated user extracted from JWT."""
    id: str
    email: str
    role: str  # 'admin' | 'teacher' | 'student'
    full_name: Optional[str] = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """
    Validate the Supabase JWT and return the current user.
    """
    settings = get_settings()
    token = credentials.credentials
    supabase = get_supabase_admin()

    user_id = None
    try:
        # First try Supabase SDK get_user validation
        user_res = supabase.auth.get_user(token)
        if user_res and user_res.user:
            user_id = str(user_res.user.id)
    except Exception:
        pass

    if not user_id:
        try:
            # Fallback to local JWT decode
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            user_id = payload.get("sub")
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token: {str(e)}",
            )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token: missing user ID",
        )

    # Look up user profile from database without .single() to avoid 500 APIError on missing profile
    try:
        result = (
            supabase.table("profiles")
            .select("id, email, full_name, role")
            .eq("id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found",
            )
        profile = result.data[0]
        return CurrentUser(
            id=profile["id"],
            email=profile["email"],
            role=profile["role"],
            full_name=profile.get("full_name"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error fetching profile: {str(e)}",
        )


def require_role(*allowed_roles: str):
    """
    Factory for role-based access control dependencies.
    
    Usage in a route:
        @router.get("/admin-only")
        async def admin_endpoint(user: CurrentUser = Depends(require_role("admin"))):
            ...
        
        @router.get("/teachers-and-admins")
        async def endpoint(user: CurrentUser = Depends(require_role("admin", "teacher"))):
            ...
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {current_user.role}",
            )
        return current_user

    return role_checker
