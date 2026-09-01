"""
Academix AI — Users Router

Admin endpoints for user management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.dependencies import require_role, CurrentUser
from app.database import get_supabase_admin
from app.models.user import UserResponse, UserRoleUpdate

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role: admin, teacher, student"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """List all users (admin only). Optionally filter by role or search."""
    supabase = get_supabase_admin()
    query = supabase.table("profiles").select("*").order("full_name")

    if role:
        query = query.eq("role", role)
    if search:
        query = query.or_(f"full_name.ilike.%{search}%,email.ilike.%{search}%")

    result = query.execute()
    return result.data or []


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Get a single user's profile (admin only)."""
    supabase = get_supabase_admin()
    result = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return result.data


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    data: UserRoleUpdate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Update a user's role (admin only)."""
    if data.role not in ("admin", "teacher", "student"):
        raise HTTPException(status_code=400, detail="Invalid role")

    supabase = get_supabase_admin()
    result = supabase.table("profiles").update({"role": data.role}).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return result.data[0]


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Delete a user account (admin only). Also removes from Supabase Auth."""
    supabase = get_supabase_admin()

    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Delete from Supabase Auth (cascade deletes profile)
    supabase.auth.admin.delete_user(user_id)
    return {"message": "User deleted successfully"}


@router.get("/stats/summary")
async def get_user_stats(
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Get user count statistics (admin dashboard)."""
    supabase = get_supabase_admin()

    total = supabase.table("profiles").select("id", count="exact").execute()
    admins = supabase.table("profiles").select("id", count="exact").eq("role", "admin").execute()
    teachers = supabase.table("profiles").select("id", count="exact").eq("role", "teacher").execute()
    students = supabase.table("profiles").select("id", count="exact").eq("role", "student").execute()

    return {
        "total": total.count or 0,
        "admins": admins.count or 0,
        "teachers": teachers.count or 0,
        "students": students.count or 0,
    }
