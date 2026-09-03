"""
Academix AI — Scheduler Router

Calendar event endpoints with conflict detection.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.dependencies import get_current_user, require_role, CurrentUser
from app.models.scheduler import EventCreate, EventUpdate, EventResponse, ConflictWarning
from app.services import scheduler_service, notice_service

router = APIRouter()


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    start_date: Optional[str] = Query(None, description="ISO date string filter start"),
    end_date: Optional[str] = Query(None, description="ISO date string filter end"),
    course_id: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List events for the current user's calendar."""
    return await scheduler_service.list_events(
        user_id=current_user.id,
        role=current_user.role,
        start_date=start_date,
        end_date=end_date,
        course_id=course_id,
    )


@router.post("/events", response_model=EventResponse)
async def create_event(
    data: EventCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Create a calendar event.
    - Admin/Teacher: can create any event type (lecture, exam, meeting, other)
    - Student: can only create meeting and other
    """
    # Restrict students to meeting and other only
    if current_user.role == "student" and data.event_type not in ("meeting", "other"):
        raise HTTPException(
            status_code=403,
            detail="Students can only create meeting and other events."
        )
    # Holiday events are admin/teacher only
    if data.event_type == "holiday" and current_user.role not in ("admin", "teacher"):
        raise HTTPException(
            status_code=403,
            detail="Only admin and teachers can create holiday events."
        )

    result = await scheduler_service.create_event(
        created_by=current_user.id,
        title=data.title,
        event_type=data.event_type,
        start_at=data.start_at.isoformat(),
        end_at=data.end_at.isoformat(),
        course_id=data.course_id or None,
        description=data.description,
        color=data.color,
        location=data.location,
    )

    # Notify everyone about the new event
    try:
        await notice_service.create_system_notice(
            title=f"New event: {data.title}",
            body=f"{data.event_type.capitalize()} scheduled for {data.start_at.strftime('%b %d, %Y at %I:%M %p')}",
            notice_type="event",
            course_id=data.course_id or None,
            posted_by=current_user.id,
        )
    except Exception:
        pass  # Don't fail event creation if notice fails

    return result


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await scheduler_service.get_event(event_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    data: EventUpdate,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    result = await scheduler_service.update_event(
        event_id, data.model_dump(exclude_none=True)
    )

    # Notify about changes
    try:
        event = await scheduler_service.get_event(event_id)
        if event:
            await notice_service.create_system_notice(
                title=f"Event updated: {event['title']}",
                body="An event on your calendar has been modified",
                notice_type="event",
                course_id=event.get("course_id"),
                posted_by=current_user.id,
            )
    except Exception:
        pass

    return result


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    # Notify before deleting
    try:
        event = await scheduler_service.get_event(event_id)
        if event:
            await notice_service.create_system_notice(
                title=f"Event cancelled: {event['title']}",
                body="A scheduled event has been cancelled",
                notice_type="event",
                course_id=event.get("course_id"),
                posted_by=current_user.id,
            )
    except Exception:
        pass

    await scheduler_service.delete_event(event_id)
    return {"message": "Event deleted"}


@router.post("/events/check-conflicts", response_model=ConflictWarning)
async def check_conflicts(
    course_id: str,
    start_at: str,
    end_at: str,
    section_id: Optional[str] = None,
    exclude_event_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """Check for scheduling conflicts before creating/updating an event."""
    conflicts = await scheduler_service.check_conflicts(
        course_id, section_id, start_at, end_at, exclude_event_id
    )
    return ConflictWarning(
        has_conflict=len(conflicts) > 0,
        conflicting_events=conflicts,
        message=f"Found {len(conflicts)} conflicting event(s)" if conflicts else None,
    )
