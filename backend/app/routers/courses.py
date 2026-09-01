"""
Academix AI — Courses Router

Endpoints for departments, courses, sections, and enrollments.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from app.dependencies import get_current_user, require_role, CurrentUser
from app.models.course import (
    DepartmentCreate, DepartmentResponse,
    CourseCreate, CourseUpdate, CourseResponse,
    SectionCreate, SectionResponse,
    EnrollmentCreate, BulkEnrollmentCreate, EnrollmentResponse,
)
from app.services import course_service

router = APIRouter()


# ─── Departments ─────────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(current_user: CurrentUser = Depends(get_current_user)):
    return await course_service.list_departments()


@router.post("/departments", response_model=DepartmentResponse)
async def create_department(
    data: DepartmentCreate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    return await course_service.create_department(data.name, data.code)


# ─── Courses ─────────────────────────────────────────────────

@router.get("/", response_model=list[CourseResponse])
async def list_courses(current_user: CurrentUser = Depends(get_current_user)):
    """List courses for the current user (enrolled courses, or all for admin)."""
    return await course_service.list_courses(
        user_id=current_user.id,
        role=current_user.role,
    )


@router.post("/", response_model=CourseResponse)
async def create_course(
    data: CourseCreate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    return await course_service.create_course(
        data.model_dump(), created_by=current_user.id
    )


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    course = await course_service.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    data: CourseUpdate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    return await course_service.update_course(
        course_id, data.model_dump(exclude_none=True)
    )


# ─── Sections ────────────────────────────────────────────────

@router.get("/{course_id}/sections", response_model=list[SectionResponse])
async def list_sections(
    course_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await course_service.list_sections(course_id)


@router.post("/{course_id}/sections", response_model=SectionResponse)
async def create_section(
    course_id: str,
    data: SectionCreate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    return await course_service.create_section(course_id, data.name)


# ─── Enrollments ─────────────────────────────────────────────

@router.get("/{course_id}/enrollments", response_model=list[EnrollmentResponse])
async def list_enrollments(
    course_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the People tab — all enrolled users for a course."""
    return await course_service.get_course_enrollments(course_id)


@router.post("/{course_id}/enroll", response_model=EnrollmentResponse)
async def enroll_user(
    course_id: str,
    data: EnrollmentCreate,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    return await course_service.enroll_user(
        course_id, data.user_id, data.role, data.section_id
    )


@router.post("/{course_id}/enroll/bulk")
async def bulk_enroll(
    course_id: str,
    data: BulkEnrollmentCreate,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    results = await course_service.bulk_enroll(
        course_id, data.user_ids, data.role, data.section_id
    )
    return {"enrolled": len(results), "enrollments": results}


@router.delete("/{course_id}/enroll/{user_id}")
async def unenroll_user(
    course_id: str,
    user_id: str,
    current_user: CurrentUser = Depends(require_role("admin")),
):
    await course_service.unenroll_user(course_id, user_id)
    return {"message": "User unenrolled successfully"}
