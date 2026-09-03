"""
Academix AI — Scheduler Models (Pydantic Schemas)
"""

from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class EventCreate(BaseModel):
    course_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: str  # 'lecture' | 'meeting' | 'exam' | 'holiday' | 'other'
    start_at: datetime
    end_at: datetime
    color: Optional[str] = None
    location: Optional[str] = None
    invitee_id: Optional[str] = None  # For meetings: the person you're meeting
    semester: Optional[str] = None  # For holidays: 'everyone' or '1'-'10'

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v):
        allowed = {"lecture", "meeting", "exam", "assignment_due", "holiday", "other"}
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
    color: Optional[str] = None
    location: Optional[str] = None


class EventResponse(BaseModel):
    id: str
    course_id: Optional[str] = None
    creator_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: str
    start_at: datetime
    end_at: datetime
    color: str = "#4285F4"
    location: Optional[str] = None
    created_at: Optional[datetime] = None
    # Joined
    course_name: Optional[str] = None
    creator_name: Optional[str] = None


class ConflictWarning(BaseModel):
    """Returned when a new event overlaps with existing events."""
    has_conflict: bool
    conflicting_events: list[EventResponse] = []
    message: Optional[str] = None


# Default colors for event types
EVENT_TYPE_COLORS = {
    "lecture": "#FBC02D",       # Yellow
    "meeting": "#4285F4",      # Blue
    "exam": "#DB4437",         # Red
    "assignment_due": "#F4B400", # Yellow/Orange
    "holiday": "#0F9D58",      # Green
    "other": "#9E9E9E",        # Grey
}
