"""
Academix AI — Course Service

Business logic for departments, courses, sections, and enrollments.
"""

from typing import Optional
from app.database import get_supabase_admin
from app.utils.helpers import generate_course_color


async def list_departments() -> list[dict]:
    # Return distinct department names from courses
    supabase = get_supabase_admin()
    result = supabase.table("courses").select("department_name").execute()
    deps = list(set([c["department_name"] for c in result.data if c.get("department_name")]))
    return [{"id": d, "name": d} for d in deps]


async def create_department(name: str, code: str) -> dict:
    # Not used since departments are just strings on courses
    return {"id": name, "name": name, "code": code}


async def list_courses(user_id: Optional[str] = None, role: Optional[str] = None) -> list[dict]:
    """
    List courses. If user_id is provided, only return enrolled courses.
    Admins see all courses.
    """
    supabase = get_supabase_admin()

    if role == "admin" or not user_id:
        result = supabase.table("courses").select("*").order("name").execute()
        courses = result.data or []
    else:
        # Get enrolled course IDs first
        enrollments = (
            supabase.table("enrollments")
            .select("course_id")
            .eq("user_id", user_id)
            .execute()
        )
        course_ids = [e["course_id"] for e in (enrollments.data or [])]
        if not course_ids:
            return []
        result = (
            supabase.table("courses")
            .select("*")
            .in_("id", course_ids)
            .order("name")
            .execute()
        )
        courses = result.data or []

    # Enrich with enrollment counts
    for course in courses:
        # Get teacher/student counts
        enrollments = (
            supabase.table("enrollments")
            .select("role")
            .eq("course_id", course["id"])
            .execute()
        )
        roles = [e["role"] for e in (enrollments.data or [])]
        course["teacher_count"] = roles.count("teacher")
        course["student_count"] = roles.count("student")

    return courses


async def create_course(data: dict, created_by: str) -> dict:
    supabase = get_supabase_admin()
    
    # Count existing courses to assign a color
    existing = supabase.table("courses").select("id", count="exact").execute()
    color = data.get("banner_color") or generate_course_color(existing.count or 0)

    result = supabase.table("courses").insert({
        "name": data["name"],
        "code": data["code"].upper(),
        "department_name": data.get("department_id") or data.get("department_name"),
        "semester": data.get("semester"),
        "description": data.get("description"),
        "banner_color": color,
    }).execute()
    return result.data[0]


async def update_course(course_id: str, updates: dict) -> dict:
    supabase = get_supabase_admin()
    clean = {k: v for k, v in updates.items() if v is not None}
    result = supabase.table("courses").update(clean).eq("id", course_id).execute()
    return result.data[0] if result.data else {}


async def get_course(course_id: str) -> Optional[dict]:
    supabase = get_supabase_admin()
    result = (
        supabase.table("courses")
        .select("*")
        .eq("id", course_id)
        .single()
        .execute()
    )
    return result.data


async def create_section(course_id: str, name: str) -> dict:
    return {"id": name, "course_id": course_id, "name": name}


async def list_sections(course_id: str) -> list[dict]:
    return []


async def enroll_user(course_id: str, user_id: str, role: str, section_id: Optional[str] = None) -> dict:
    supabase = get_supabase_admin()
    result = supabase.table("enrollments").insert({
        "course_id": course_id,
        "user_id": user_id,
        "role": role,
    }).execute()
    return result.data[0]


async def bulk_enroll(course_id: str, user_ids: list[str], role: str, section_id: Optional[str] = None) -> list[dict]:
    supabase = get_supabase_admin()
    records = [{
        "course_id": course_id,
        "user_id": uid,
        "role": role,
    } for uid in user_ids]
    result = supabase.table("enrollments").upsert(records, on_conflict="course_id,user_id").execute()
    return result.data or []


async def unenroll_user(course_id: str, user_id: str):
    supabase = get_supabase_admin()
    supabase.table("enrollments").delete().eq("course_id", course_id).eq("user_id", user_id).execute()


async def get_course_enrollments(course_id: str) -> list[dict]:
    """Get all enrollments for a course with user details (People tab)."""
    supabase = get_supabase_admin()
    result = (
        supabase.table("enrollments")
        .select("*, profiles(full_name, email, avatar_url)")
        .eq("course_id", course_id)
        .order("role")
        .execute()
    )
    enrollments = result.data or []
    for e in enrollments:
        if e.get("profiles"):
            e["user_name"] = e["profiles"]["full_name"]
            e["user_email"] = e["profiles"]["email"]
            del e["profiles"]
    return enrollments


async def check_enrollment(course_id: str, user_id: str) -> Optional[dict]:
    """Check if a user is enrolled in a course."""
    supabase = get_supabase_admin()
    result = (
        supabase.table("enrollments")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return result.data
