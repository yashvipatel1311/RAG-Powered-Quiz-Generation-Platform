"""
Academix AI — Notice Board Models (Pydantic Schemas)
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NoticeCreate(BaseModel):
    course_id: Optional[str] = None  # None = institute-wide
    title: str
    body: str
    notice_type: str = "announcement"  # announcement | assignment | grade | event | admin


class NoticeResponse(BaseModel):
    id: str
    course_id: Optional[str] = None
    author_id: Optional[str] = None
    title: str
    body: str
    notice_type: str
    created_at: Optional[datetime] = None
    is_read: bool = False
    # Joined
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    course_name: Optional[str] = None


class NoticeListResponse(BaseModel):
    notices: list[NoticeResponse]
    total: int
    unread_count: int


class MarkReadRequest(BaseModel):
    notice_ids: list[str]
