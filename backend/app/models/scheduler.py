"""
Academix AI — Scheduler Models (Pydantic Schemas)
"""

from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class EventCreate(BaseModel):
    course_id: Optional[str] = None
    section_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: str  # 'lecture' | 'meeting' | 'exam' | 'assignment_due' | 'other'
    start_at: datetime
    end_at: datetime
    is_all_day: bool = False
    is_recurring: bool = False
    recurrence_rule: Optional[dict] = None
    color: Optional[str] = None
    location: Optional[str] = None
    reminder_minutes: int = 30

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v):
        allowed = {"lecture", "meeting", "exam", "assignment_due", "other"}
        if v not in allowed:
            raise ValueError(f"event_type must be one of: {allowed}")
        return v

    @field_validator("end_at")
    @classmethod
    def validate_end_after_start(cls, v, info):
        if "start_at" in info.data and v <= info.data["start_at"]:
            raise ValueError("end_at must be after start_at")
        return v


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_all_day: Optional[bool] = None
    color: Optional[str] = None
    location: Optional[str] = None
    reminder_minutes: Optional[int] = None


class EventResponse(BaseModel):
    id: str
    course_id: Optional[str] = None
    section_id: Optional[str] = None
    created_by: str
    title: str
    description: Optional[str] = None
    event_type: str
    start_at: datetime
    end_at: datetime
    is_all_day: bool = False
    is_recurring: bool = False
    recurrence_rule: Optional[dict] = None
    color: str = "#4285F4"
    location: Optional[str] = None
    reminder_minutes: int = 30
    created_at: Optional[datetime] = None
    # Joined
    course_name: Optional[str] = None
    creator_name: Optional[str] = None


class ConflictWarning(BaseModel):
    """Returned when a new event overlaps with existing events."""
    has_conflict: bool
    conflicting_events: list[EventResponse] = []
    message: Optional[str] = None


# Default colors for event types (used by frontend too)
EVENT_TYPE_COLORS = {
    "lecture": "#4285F4",      # Google Blue
    "meeting": "#0F9D58",      # Google Green
    "exam": "#DB4437",         # Google Red
    "assignment_due": "#F4B400", # Google Yellow
    "other": "#9E9E9E",        # Grey
}
