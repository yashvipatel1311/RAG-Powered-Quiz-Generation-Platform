"""
Academix AI — Notice Board Service

Business logic for in-app notifications and announcements.
Phase 1: in-app feed only (no email delivery).
"""

from typing import Optional
from app.database import get_supabase_admin


async def create_notice(
    posted_by: str,
    title: str,
    body: str,
    notice_type: str = "announcement",
    course_id: Optional[str] = None,
    target_roles: list[str] = ["admin", "teacher", "student"],
) -> dict:
    """Create a new notice."""
    supabase = get_supabase_admin()
    result = supabase.table("notices").insert({
        "author_id": posted_by,
        "title": title,
        "body": body,
        "notice_type": notice_type,
        "course_id": course_id,
    }).execute()
    return result.data[0]


async def list_notices(
    user_id: str,
    role: str,
    course_id: Optional[str] = None,
    notice_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    List notices for a user based on their role and enrollments.
    Returns notices + unread count.
    """
    supabase = get_supabase_admin()

    # Get user's enrolled courses
    enrolled_courses = []
    if role != "admin":
        enrollments = (
            supabase.table("enrollments")
            .select("course_id")
            .eq("user_id", user_id)
            .execute()
        )
        enrolled_courses = [e["course_id"] for e in (enrollments.data or [])]

    # Build query
    query = (
        supabase.table("notices")
        .select("*, profiles(full_name, avatar_url), courses(name)")
    )

    if course_id:
        query = query.eq("course_id", course_id)
    elif role != "admin":
        # Show institute-wide notices + notices for enrolled courses
        query = query.or_(
            f"course_id.is.null,course_id.in.({','.join(enrolled_courses)})"
        ) if enrolled_courses else query.is_("course_id", "null")

    if notice_type:
        query = query.eq("notice_type", notice_type)

    # Target roles filtering removed since it's not in schema

    result = (
        query
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    notices = result.data or []

    # Get read status for this user
    notice_ids = [n["id"] for n in notices]
    if notice_ids:
        reads = (
            supabase.table("notice_reads")
            .select("notice_id")
            .eq("user_id", user_id)
            .in_("notice_id", notice_ids)
            .execute()
        )
        read_ids = set(r["notice_id"] for r in (reads.data or []))
    else:
        read_ids = set()

    # Enrich notices
    for notice in notices:
        notice["is_read"] = notice["id"] in read_ids
        if notice.get("profiles"):
            notice["author_name"] = notice["profiles"]["full_name"]
            notice["author_avatar"] = notice["profiles"].get("avatar_url")
            del notice["profiles"]
        if notice.get("courses"):
            notice["course_name"] = notice["courses"]["name"]
            del notice["courses"]

    # Count unread
    unread_count = sum(1 for n in notices if not n["is_read"])

    return {
        "notices": notices,
        "total": len(notices),
        "unread_count": unread_count,
    }


async def mark_as_read(user_id: str, notice_ids: list[str]):
    """Mark notices as read for a user."""
    supabase = get_supabase_admin()
    records = [{"notice_id": nid, "user_id": user_id} for nid in notice_ids]
    supabase.table("notice_reads").upsert(
        records, on_conflict="notice_id,user_id"
    ).execute()


async def get_unread_count(user_id: str, role: str) -> int:
    """Get total unread notice count for a user."""
    result = await list_notices(user_id, role, limit=1000)
    return result["unread_count"]


async def create_system_notice(
    title: str,
    body: str,
    notice_type: str,
    course_id: Optional[str] = None,
    posted_by: Optional[str] = None,
    target_roles: list[str] = ["admin", "teacher", "student"],
):
    """
    Create a system-generated notice (triggered by events like assignment creation, grading, etc).
    Used internally by other services to generate notifications.
    """
    supabase = get_supabase_admin()

    # Use a system user ID or the actor's ID
    poster = posted_by or "system"

    supabase.table("notices").insert({
        "author_id": poster if poster != "system" else None,
        "title": title,
        "body": body,
        "notice_type": notice_type,
        "course_id": course_id,
    }).execute()
