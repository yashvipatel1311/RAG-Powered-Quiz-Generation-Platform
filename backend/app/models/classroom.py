"""
Academix AI — Classroom Models (Pydantic Schemas)

Covers: Announcements, Materials, Assignments, Submissions, Grades
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Announcement ---

class AnnouncementCreate(BaseModel):
    course_id: str
    text: str
    attachment_urls: list[str] = []


class AnnouncementResponse(BaseModel):
    id: str
    course_id: str
    posted_by: str
    text: str
    attachment_urls: list[str] = []
    posted_at: Optional[datetime] = None
    # Joined
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None


# --- Material ---

class MaterialCreate(BaseModel):
    course_id: str
    title: str
    description: Optional[str] = None
    topic_tag: Optional[str] = None
    # file_url is set by the backend after upload
    source_type: str = "notes"  # 'notes' | 'textbook' | 'pyq'
    exam_type: Optional[str] = None  # 'internal' | 'external' (for PYQs)
    year: Optional[int] = None  # for PYQs


class MaterialResponse(BaseModel):
    id: str
    course_id: str
    uploaded_by: str
    title: str
    description: Optional[str] = None
    file_url: str
    file_name: str
    file_size: Optional[int] = None
    topic_tag: Optional[str] = None
    created_at: Optional[datetime] = None
    # Joined
    uploader_name: Optional[str] = None
    # RAG status
    ingestion_status: Optional[str] = None


# --- Assignment ---

class AssignmentCreate(BaseModel):
    course_id: str
    title: str
    instructions: Optional[str] = None
    attachment_urls: list[str] = []
    due_at: Optional[datetime] = None
    max_points: int = 100
    topic_tag: Optional[str] = None


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    instructions: Optional[str] = None
    attachment_urls: Optional[list[str]] = None
    due_at: Optional[datetime] = None
    max_points: Optional[int] = None
    topic_tag: Optional[str] = None


class AssignmentResponse(BaseModel):
    id: str
    course_id: str
    created_by: str
    title: str
    instructions: Optional[str] = None
    attachment_urls: list[str] = []
    due_at: Optional[datetime] = None
    max_points: int = 100
    topic_tag: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined
    author_name: Optional[str] = None
    submission_count: Optional[int] = None
    graded_count: Optional[int] = None


# --- Submission ---

class SubmissionCreate(BaseModel):
    assignment_id: str
    text_response: Optional[str] = None
    # file_url is set by backend after upload


class SubmissionResponse(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    file_url: Optional[str] = None
    text_response: Optional[str] = None
    submitted_at: Optional[datetime] = None
    status: str = "submitted"
    # Joined
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    # Grade info
    grade: Optional["GradeResponse"] = None


# --- Grade ---

class GradeCreate(BaseModel):
    submission_id: str
    points_awarded: int
    feedback_text: Optional[str] = None


class GradeResponse(BaseModel):
    id: str
    submission_id: str
    points_awarded: int
    feedback_text: Optional[str] = None
    graded_by: str
    graded_at: Optional[datetime] = None


# --- Stream Item (unified feed) ---

class StreamItem(BaseModel):
    """Unified item for the course stream feed."""
    id: str
    type: str  # 'announcement' | 'material' | 'assignment'
    title: Optional[str] = None
    text: Optional[str] = None
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    created_at: Optional[datetime] = None
    # Type-specific fields
    due_at: Optional[datetime] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    max_points: Optional[int] = None


# Update forward refs
SubmissionResponse.model_rebuild()
