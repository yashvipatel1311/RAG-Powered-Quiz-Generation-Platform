"""
Academix AI — Classroom Service

Business logic for the Classroom module (Google Classroom parity):
  - Announcements (Stream)
  - Materials (Classwork)
  - Assignments + Submissions + Grades
"""

from typing import Optional
from datetime import datetime, timezone
from app.database import get_supabase_admin


# ─── Announcements (Stream) ─────────────────────────────────

async def create_announcement(course_id: str, posted_by: str, text: str, attachment_urls: list[str] = []) -> dict:
    supabase = get_supabase_admin()
    result = supabase.table("announcements").insert({
        "course_id": course_id,
        "posted_by": posted_by,
        "text": text,
        "attachment_urls": attachment_urls,
    }).execute()
    return result.data[0]


async def list_announcements(course_id: str) -> list[dict]:
    supabase = get_supabase_admin()
    result = (
        supabase.table("announcements")
        .select("*, profiles!posted_by(full_name, avatar_url)")
        .eq("course_id", course_id)
        .order("posted_at", desc=True)
        .execute()
    )
    items = result.data or []
    for item in items:
        if item.get("profiles"):
            item["author_name"] = item["profiles"]["full_name"]
            item["author_avatar"] = item["profiles"].get("avatar_url")
            del item["profiles"]
    return items


# ─── Materials (Classwork) ───────────────────────────────────

async def create_material(
    course_id: str,
    uploaded_by: str,
    title: str,
    file_url: str,
    file_name: str,
    file_size: Optional[int] = None,
    description: Optional[str] = None,
    topic_tag: Optional[str] = None,
) -> dict:
    supabase = get_supabase_admin()
    result = supabase.table("materials").insert({
        "course_id": course_id,
        "uploaded_by": uploaded_by,
        "title": title,
        "file_url": file_url,
        "file_name": file_name,
        "file_size": file_size,
        "description": description,
        "topic_tag": topic_tag,
    }).execute()
    return result.data[0]


async def list_materials(course_id: str, topic_tag: Optional[str] = None) -> list[dict]:
    supabase = get_supabase_admin()
    query = (
        supabase.table("materials")
        .select("*, profiles!uploaded_by(full_name)")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
    )
    if topic_tag:
        query = query.eq("topic_tag", topic_tag)

    result = query.execute()
    items = result.data or []
    for item in items:
        if item.get("profiles"):
            item["uploader_name"] = item["profiles"]["full_name"]
            del item["profiles"]
    return items


# ─── Assignments ─────────────────────────────────────────────

async def create_assignment(
    course_id: str,
    created_by: str,
    title: str,
    instructions: Optional[str] = None,
    attachment_urls: list[str] = [],
    due_at: Optional[str] = None,
    max_points: int = 100,
    topic_tag: Optional[str] = None,
) -> dict:
    supabase = get_supabase_admin()
    result = supabase.table("assignments").insert({
        "course_id": course_id,
        "created_by": created_by,
        "title": title,
        "instructions": instructions,
        "attachment_urls": attachment_urls,
        "due_at": due_at,
        "max_points": max_points,
        "topic_tag": topic_tag,
    }).execute()
    return result.data[0]


async def list_assignments(course_id: str) -> list[dict]:
    supabase = get_supabase_admin()
    result = (
        supabase.table("assignments")
        .select("*, profiles!created_by(full_name)")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .execute()
    )
    items = result.data or []
    for item in items:
        if item.get("profiles"):
            item["author_name"] = item["profiles"]["full_name"]
            del item["profiles"]

        # Get submission stats
        subs = (
            supabase.table("submissions")
            .select("status", count="exact")
            .eq("assignment_id", item["id"])
            .execute()
        )
        item["submission_count"] = subs.count or 0
        graded = (
            supabase.table("submissions")
            .select("id", count="exact")
            .eq("assignment_id", item["id"])
            .eq("status", "graded")
            .execute()
        )
        item["graded_count"] = graded.count or 0

    return items


async def get_assignment(assignment_id: str) -> Optional[dict]:
    supabase = get_supabase_admin()
    result = (
        supabase.table("assignments")
        .select("*, profiles!created_by(full_name)")
        .eq("id", assignment_id)
        .single()
        .execute()
    )
    if result.data and result.data.get("profiles"):
        result.data["author_name"] = result.data["profiles"]["full_name"]
        del result.data["profiles"]
    return result.data


async def update_assignment(assignment_id: str, updates: dict) -> dict:
    supabase = get_supabase_admin()
    clean = {k: v for k, v in updates.items() if v is not None}
    result = supabase.table("assignments").update(clean).eq("id", assignment_id).execute()
    return result.data[0] if result.data else {}


# ─── Submissions ─────────────────────────────────────────────

async def create_submission(
    assignment_id: str,
    student_id: str,
    file_url: Optional[str] = None,
    text_response: Optional[str] = None,
) -> dict:
    supabase = get_supabase_admin()

    # Check if late
    assignment = await get_assignment(assignment_id)
    status = "submitted"
    if assignment and assignment.get("due_at"):
        due = datetime.fromisoformat(assignment["due_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > due:
            status = "late"

    result = supabase.table("submissions").upsert({
        "assignment_id": assignment_id,
        "student_id": student_id,
        "file_url": file_url,
        "text_response": text_response,
        "status": status,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="assignment_id,student_id").execute()
    return result.data[0]


async def list_submissions(assignment_id: str) -> list[dict]:
    """List all submissions for an assignment (teacher view)."""
    supabase = get_supabase_admin()
    result = (
        supabase.table("submissions")
        .select("*, profiles!student_id(full_name, email), grades(*)")
        .eq("assignment_id", assignment_id)
        .order("submitted_at", desc=True)
        .execute()
    )
    items = result.data or []
    for item in items:
        if item.get("profiles"):
            item["student_name"] = item["profiles"]["full_name"]
            item["student_email"] = item["profiles"]["email"]
            del item["profiles"]
        if item.get("grades") and len(item["grades"]) > 0:
            item["grade"] = item["grades"][0]
            del item["grades"]
        else:
            item["grade"] = None
            if "grades" in item:
                del item["grades"]
    return items


async def get_student_submission(assignment_id: str, student_id: str) -> Optional[dict]:
    supabase = get_supabase_admin()
    result = (
        supabase.table("submissions")
        .select("*, grades(*)")
        .eq("assignment_id", assignment_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    if result.data:
        if result.data.get("grades") and len(result.data["grades"]) > 0:
            result.data["grade"] = result.data["grades"][0]
        else:
            result.data["grade"] = None
        if "grades" in result.data:
            del result.data["grades"]
    return result.data


# ─── Grades ──────────────────────────────────────────────────

async def grade_submission(submission_id: str, graded_by: str, points_awarded: int, feedback_text: Optional[str] = None) -> dict:
    supabase = get_supabase_admin()

    # Upsert grade
    grade_result = supabase.table("grades").upsert({
        "submission_id": submission_id,
        "points_awarded": points_awarded,
        "feedback_text": feedback_text,
        "graded_by": graded_by,
    }, on_conflict="submission_id").execute()

    # Update submission status to graded
    supabase.table("submissions").update({"status": "graded"}).eq("id", submission_id).execute()

    return grade_result.data[0] if grade_result.data else {}


# ─── Stream (Unified Feed) ──────────────────────────────────

async def get_course_stream(course_id: str, limit: int = 50) -> list[dict]:
    """
    Get a unified, reverse-chronological stream of all activity for a course.
    Merges announcements, materials, and assignments into one feed.
    """
    supabase = get_supabase_admin()

    # Fetch all three types
    announcements = (
        supabase.table("announcements")
        .select("id, text, posted_at, posted_by, profiles!posted_by(full_name, avatar_url)")
        .eq("course_id", course_id)
        .order("posted_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []

    materials_data = (
        supabase.table("materials")
        .select("id, title, file_url, file_name, created_at, uploaded_by, profiles!uploaded_by(full_name, avatar_url)")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []

    assignments_data = (
        supabase.table("assignments")
        .select("id, title, due_at, max_points, created_at, created_by, profiles!created_by(full_name, avatar_url)")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []

    # Merge into stream items
    stream = []

    for a in announcements:
        profile = a.get("profiles", {})
        stream.append({
            "id": a["id"],
            "type": "announcement",
            "text": a["text"],
            "author_name": profile.get("full_name"),
            "author_avatar": profile.get("avatar_url"),
            "created_at": a["posted_at"],
        })

    for m in materials_data:
        profile = m.get("profiles", {})
        stream.append({
            "id": m["id"],
            "type": "material",
            "title": m["title"],
            "file_url": m["file_url"],
            "file_name": m["file_name"],
            "author_name": profile.get("full_name"),
            "author_avatar": profile.get("avatar_url"),
            "created_at": m["created_at"],
        })

    for a in assignments_data:
        profile = a.get("profiles", {})
        stream.append({
            "id": a["id"],
            "type": "assignment",
            "title": a["title"],
            "due_at": a.get("due_at"),
            "max_points": a.get("max_points"),
            "author_name": profile.get("full_name"),
            "author_avatar": profile.get("avatar_url"),
            "created_at": a["created_at"],
        })

    # Sort by created_at descending
    stream.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return stream[:limit]
