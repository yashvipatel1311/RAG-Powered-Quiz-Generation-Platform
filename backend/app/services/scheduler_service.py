"""
Academix AI — Scheduler Service

Business logic for the native calendar/scheduler module.
Google Calendar-style event management with conflict detection.
"""

from typing import Optional
from datetime import datetime
from app.database import get_supabase_admin
from app.models.scheduler import EVENT_TYPE_COLORS


async def create_event(
    created_by: str,
    title: str,
    event_type: str,
    start_at: str,
    end_at: str,
    course_id: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    """Create a new calendar event."""
    supabase = get_supabase_admin()

    # Auto-assign color based on event type if not specified
    if not color:
        color = EVENT_TYPE_COLORS.get(event_type, "#4285F4")

    result = supabase.table("calendar_events").insert({
        "creator_id": created_by,
        "title": title,
        "event_type": event_type,
        "start_at": start_at,
        "end_at": end_at,
        "course_id": course_id,
        "description": description,
        "color": color,
        "location": location,
    }).execute()
    return result.data[0]


async def list_events(
    user_id: str,
    role: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    course_id: Optional[str] = None,
) -> list[dict]:
    """
    List ALL events for a user. Everyone sees all events so that
    schedules, exams, lectures, and meetings are visible across accounts.
    """
    supabase = get_supabase_admin()

    query = supabase.table("calendar_events").select("*, courses(name), profiles(full_name)")

    # Apply date filters
    if start_date:
        query = query.gte("start_at", start_date)
    if end_date:
        query = query.lte("end_at", end_date)
    if course_id:
        query = query.eq("course_id", course_id)

    result = query.order("start_at").execute()
    events = result.data or []

    for event in events:
        if event.get("courses"):
            event["course_name"] = event["courses"]["name"]
            del event["courses"]
        if event.get("profiles"):
            event["creator_name"] = event["profiles"]["full_name"]
            del event["profiles"]

    return events


async def get_event(event_id: str) -> Optional[dict]:
    supabase = get_supabase_admin()
    result = (
        supabase.table("calendar_events")
        .select("*, courses(name), profiles(full_name)")
        .eq("id", event_id)
        .single()
        .execute()
    )
    if result.data:
        if result.data.get("courses"):
            result.data["course_name"] = result.data["courses"]["name"]
            del result.data["courses"]
        if result.data.get("profiles"):
            result.data["creator_name"] = result.data["profiles"]["full_name"]
            del result.data["profiles"]
    return result.data


async def update_event(event_id: str, updates: dict) -> dict:
    supabase = get_supabase_admin()
    clean = {k: v for k, v in updates.items() if v is not None}
    result = supabase.table("calendar_events").update(clean).eq("id", event_id).execute()
    return result.data[0] if result.data else {}


async def delete_event(event_id: str):
    supabase = get_supabase_admin()
    supabase.table("calendar_events").delete().eq("id", event_id).execute()


async def check_conflicts(
    course_id: str,
    section_id: Optional[str],
    start_at: str,
    end_at: str,
    exclude_event_id: Optional[str] = None,
) -> list[dict]:
    """
    Check for scheduling conflicts for a given time range.
    Returns any overlapping events for the same course.
    """
    supabase = get_supabase_admin()

    query = (
        supabase.table("calendar_events")
        .select("*")
        .eq("course_id", course_id)
        .lt("start_at", end_at)
        .gt("end_at", start_at)
    )

    if exclude_event_id:
        query = query.neq("id", exclude_event_id)

    result = query.execute()
    return result.data or []
