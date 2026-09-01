"""
Academix AI — Auth Service

Handles user authentication via Supabase Auth.
"""

from typing import Optional

from app.database import get_supabase, get_supabase_admin
from app.models.user import LoginRequest, SignUpRequest, UserResponse


async def sign_up_user(data: SignUpRequest) -> dict:
    """
    Create a new user via Supabase Auth.
    The database trigger (handle_new_user) auto-creates the profile row.
    """
    supabase = get_supabase_admin()

    # Create user in Supabase Auth with metadata
    result = supabase.auth.admin.create_user({
        "email": data.email,
        "password": data.password,
        "email_confirm": True,  # Auto-confirm for admin-created users
        "user_metadata": {
            "full_name": data.full_name,
            "role": data.role,
        },
    })

    user = result.user

    # Update profile with additional fields if needed
    if data.department:
        supabase.table("profiles").update({
            "department": data.department,
        }).eq("id", str(user.id)).execute()

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": data.full_name,
        "role": data.role,
    }


async def sign_in_user(data: LoginRequest) -> dict:
    """
    Sign in a user and return access + refresh tokens.
    """
    supabase = get_supabase()

    result = supabase.auth.sign_in_with_password({
        "email": data.email,
        "password": data.password,
    })

    session = result.session
    user = result.user

    # Fetch profile for role info
    profile = (
        get_supabase_admin()
        .table("profiles")
        .select("*")
        .eq("id", str(user.id))
        .execute()
    )

    user_profile = profile.data[0] if profile.data else {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.user_metadata.get("full_name", user.email),
        "role": user.user_metadata.get("role", "student"),
    }

    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "user": user_profile,
    }


async def refresh_session(refresh_token: str) -> dict:
    """Refresh an expired access token."""
    supabase = get_supabase()
    result = supabase.auth.refresh_session(refresh_token)
    return {
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
    }


async def get_user_profile(user_id: str) -> Optional[dict]:
    """Get a user's profile by ID."""
    supabase = get_supabase_admin()
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


async def update_user_profile(user_id: str, updates: dict) -> dict:
    """Update a user's profile."""
    supabase = get_supabase_admin()
    # Filter out None values
    clean_updates = {k: v for k, v in updates.items() if v is not None}
    if not clean_updates:
        return await get_user_profile(user_id)

    result = (
        supabase.table("profiles")
        .update(clean_updates)
        .eq("id", user_id)
        .execute()
    )
    return result.data[0] if result.data else {}
