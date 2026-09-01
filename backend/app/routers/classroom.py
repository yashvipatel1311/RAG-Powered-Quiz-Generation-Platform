"""
Academix AI — Classroom Router

Endpoints for the full Classroom module:
  Stream, Materials, Assignments, Submissions, Grades
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from typing import Optional

from app.dependencies import get_current_user, require_role, CurrentUser
from app.models.classroom import (
    AnnouncementCreate, AnnouncementResponse,
    MaterialCreate, MaterialResponse,
    AssignmentCreate, AssignmentUpdate, AssignmentResponse,
    SubmissionCreate, SubmissionResponse,
    GradeCreate, GradeResponse,
    StreamItem,
)
from app.services import classroom_service, notice_service
from app.services.rag.ingestion import ingest_document
from app.database import get_supabase_admin

router = APIRouter()


# ─── Stream ──────────────────────────────────────────────────

@router.get("/{course_id}/stream", response_model=list[StreamItem])
async def get_stream(
    course_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the course stream (reverse-chronological feed of all activity)."""
    return await classroom_service.get_course_stream(course_id)


# ─── Announcements ───────────────────────────────────────────

@router.post("/{course_id}/announcements", response_model=AnnouncementResponse)
async def create_announcement(
    course_id: str,
    data: AnnouncementCreate,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    result = await classroom_service.create_announcement(
        course_id, current_user.id, data.text, data.attachment_urls
    )
    # Create notice for enrolled students
    await notice_service.create_system_notice(
        title=f"New announcement in course",
        body=data.text[:200],
        notice_type="announcement",
        course_id=course_id,
        posted_by=current_user.id,
        target_roles=["student"],
    )
    return result


@router.get("/{course_id}/announcements", response_model=list[AnnouncementResponse])
async def list_announcements(
    course_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await classroom_service.list_announcements(course_id)


# ─── Materials ───────────────────────────────────────────────

@router.post("/{course_id}/materials", response_model=MaterialResponse)
async def upload_material(
    course_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    topic_tag: Optional[str] = Form(None),
    source_type: str = Form("notes"),
    exam_type: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """
    Upload a material file + auto-trigger RAG ingestion.
    This is the key integration point between Classroom and the RAG engine.
    """
    supabase = get_supabase_admin()

    # 1. Upload file to Supabase Storage
    bucket = "pyq-papers" if source_type == "pyq" else "course-materials"
    storage_path = f"{course_id}/{file.filename}"
    file_bytes = await file.read()

    supabase.storage.from_(bucket).upload(
        storage_path, file_bytes,
        {"content-type": file.content_type or "application/octet-stream"}
    )

    file_url = f"{bucket}/{storage_path}"

    # 2. Create material record
    material = await classroom_service.create_material(
        course_id=course_id,
        uploaded_by=current_user.id,
        title=title,
        file_url=file_url,
        file_name=file.filename,
        file_size=len(file_bytes),
        description=description,
        topic_tag=topic_tag,
    )

    # 3. Create content_document record for RAG tracking
    doc_result = supabase.table("content_documents").insert({
        "course_id": course_id,
        "uploaded_by": current_user.id,
        "file_url": file_url,
        "file_name": file.filename,
        "file_size": len(file_bytes),
        "source_type": source_type,
        "exam_type": exam_type,
        "year": year,
        "status": "pending",
    }).execute()

    document_id = doc_result.data[0]["id"]

    # 4. Trigger async RAG ingestion pipeline
    background_tasks.add_task(
        ingest_document,
        document_id=document_id,
        course_id=course_id,
        file_url=file_url,
        file_name=file.filename,
        source_type=source_type,
        exam_type=exam_type,
    )

    # 5. Create notice
    await notice_service.create_system_notice(
        title=f"New material: {title}",
        body=f"New {source_type} uploaded for your course",
        notice_type="announcement",
        course_id=course_id,
        posted_by=current_user.id,
        target_roles=["student"],
    )

    material["ingestion_status"] = "pending"
    return material


@router.get("/{course_id}/materials", response_model=list[MaterialResponse])
async def list_materials(
    course_id: str,
    topic_tag: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await classroom_service.list_materials(course_id, topic_tag)


# ─── Assignments ─────────────────────────────────────────────

@router.post("/{course_id}/assignments", response_model=AssignmentResponse)
async def create_assignment(
    course_id: str,
    data: AssignmentCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    result = await classroom_service.create_assignment(
        course_id=course_id,
        created_by=current_user.id,
        title=data.title,
        instructions=data.instructions,
        attachment_urls=data.attachment_urls,
        due_at=data.due_at.isoformat() if data.due_at else None,
        max_points=data.max_points,
        topic_tag=data.topic_tag,
    )

    # Auto-create scheduler event for assignment due date
    if data.due_at:
        from app.services import scheduler_service
        await scheduler_service.create_event(
            created_by=current_user.id,
            title=f"Due: {data.title}",
            event_type="assignment_due",
            start_at=data.due_at.isoformat(),
            end_at=data.due_at.isoformat(),
            course_id=course_id,
        )

    # Create notice
    await notice_service.create_system_notice(
        title=f"New assignment: {data.title}",
        body=data.instructions[:200] if data.instructions else "A new assignment has been posted",
        notice_type="assignment",
        course_id=course_id,
        posted_by=current_user.id,
        target_roles=["student"],
    )

    return result


@router.get("/{course_id}/assignments", response_model=list[AssignmentResponse])
async def list_assignments(
    course_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await classroom_service.list_assignments(course_id)


@router.get("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    course_id: str,
    assignment_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await classroom_service.get_assignment(assignment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return result


@router.patch("/{course_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    course_id: str,
    assignment_id: str,
    data: AssignmentUpdate,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    return await classroom_service.update_assignment(
        assignment_id, data.model_dump(exclude_none=True)
    )


# ─── Submissions ─────────────────────────────────────────────

@router.post("/{course_id}/assignments/{assignment_id}/submit", response_model=SubmissionResponse)
async def submit_assignment(
    course_id: str,
    assignment_id: str,
    file: Optional[UploadFile] = File(None),
    text_response: Optional[str] = Form(None),
    current_user: CurrentUser = Depends(require_role("student")),
):
    """Submit an assignment (student only). Can upload a file and/or text response."""
    file_url = None

    if file:
        supabase = get_supabase_admin()
        storage_path = f"{assignment_id}/{current_user.id}/{file.filename}"
        file_bytes = await file.read()
        supabase.storage.from_("submissions").upload(
            storage_path, file_bytes,
            {"content-type": file.content_type or "application/octet-stream"}
        )
        file_url = f"submissions/{storage_path}"

    return await classroom_service.create_submission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        file_url=file_url,
        text_response=text_response,
    )


@router.get("/{course_id}/assignments/{assignment_id}/submissions", response_model=list[SubmissionResponse])
async def list_submissions(
    course_id: str,
    assignment_id: str,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """List all submissions for an assignment (teacher view)."""
    return await classroom_service.list_submissions(assignment_id)


@router.get("/{course_id}/assignments/{assignment_id}/my-submission", response_model=SubmissionResponse)
async def get_my_submission(
    course_id: str,
    assignment_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the current student's submission for an assignment."""
    result = await classroom_service.get_student_submission(assignment_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="No submission found")
    return result


# ─── Grades ──────────────────────────────────────────────────

@router.post("/{course_id}/grades", response_model=GradeResponse)
async def grade_submission(
    course_id: str,
    data: GradeCreate,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """Grade a student's submission (teacher only)."""
    result = await classroom_service.grade_submission(
        submission_id=data.submission_id,
        graded_by=current_user.id,
        points_awarded=data.points_awarded,
        feedback_text=data.feedback_text,
    )

    # Notify student
    supabase = get_supabase_admin()
    submission = supabase.table("submissions").select("student_id, assignment_id").eq("id", data.submission_id).single().execute()
    if submission.data:
        assignment = supabase.table("assignments").select("title").eq("id", submission.data["assignment_id"]).single().execute()
        await notice_service.create_system_notice(
            title=f"Grade posted: {assignment.data['title'] if assignment.data else 'Assignment'}",
            body=f"You received {data.points_awarded} points. {data.feedback_text or ''}",
            notice_type="grade",
            course_id=course_id,
            posted_by=current_user.id,
            target_roles=["student"],
        )

    return result
