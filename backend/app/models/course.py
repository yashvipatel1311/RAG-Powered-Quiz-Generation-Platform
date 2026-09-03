"""
Academix AI — Course & Enrollment Models (Pydantic Schemas)
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Department ---

class DepartmentCreate(BaseModel):
    name: str
    code: str


class DepartmentResponse(BaseModel):
    id: str
    name: str
    code: str
    created_at: Optional[datetime] = None


# --- Course ---

class CourseCreate(BaseModel):
    name: str
    code: str
    department_id: Optional[str] = None
    semester: Optional[int] = None
    description: Optional[str] = None
    banner_color: Optional[str] = "#4285F4"


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    semester: Optional[int] = None
    banner_color: Optional[str] = None


class CourseResponse(BaseModel):
    id: str
    name: str
    code: str
    department_id: Optional[str] = None
    semester: Optional[int] = None
    description: Optional[str] = None
    banner_color: str = "#4285F4"
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    # Joined data
    department_name: Optional[str] = None
    teacher_count: Optional[int] = None
    student_count: Optional[int] = None


# --- Section ---

class SectionCreate(BaseModel):
    course_id: str
    name: str


class SectionResponse(BaseModel):
    id: str
    course_id: str
    name: str
    created_at: Optional[datetime] = None


# --- Enrollment ---

class EnrollmentCreate(BaseModel):
    course_id: str
    user_id: str
    role: str  # 'teacher' | 'student'
    section_id: Optional[str] = None


class BulkEnrollmentCreate(BaseModel):
    """For enrolling multiple users at once."""
    course_id: str
    user_ids: list[str]
    role: str  # 'teacher' | 'student'
    section_id: Optional[str] = None


class EnrollmentResponse(BaseModel):
    id: Optional[str] = None
    course_id: str
    user_id: str
    role: str
    section_id: Optional[str] = None
    enrolled_at: Optional[datetime] = None
    # Joined data
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    course_name: Optional[str] = None
