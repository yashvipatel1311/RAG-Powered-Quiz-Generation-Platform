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

    # 1. Read file bytes
    file_bytes = await file.read()
    file_url = f"materials/{course_id}/{file.filename}"

    # 2. Upload file to Supabase Storage (with error handling)
    bucket = "course-materials"
    storage_path = f"{course_id}/{file.filename}"
    try:
        # Try to create bucket if it doesn't exist
        try:
            supabase.storage.create_bucket(bucket, options={"public": True})
        except Exception:
            pass  # Bucket already exists

        supabase.storage.from_(bucket).upload(
            storage_path, file_bytes,
            {"content-type": file.content_type or "application/octet-stream", "upsert": "true"}
        )
        file_url = f"{bucket}/{storage_path}"
    except Exception as e:
        # Storage upload failed — still save the material record without file
        file_url = f"local/{course_id}/{file.filename}"

    # 3. Create material record
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

    # 4. Create content_document record for RAG tracking (optional)
    try:
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

        # 5. Trigger async RAG ingestion pipeline
        background_tasks.add_task(
            ingest_document,
            document_id=document_id,
            course_id=course_id,
            file_url=file_url,
            file_name=file.filename,
            source_type=source_type,
            exam_type=exam_type,
        )
        material["ingestion_status"] = "pending"
    except Exception:
        material["ingestion_status"] = "skipped"

    # 6. Create notice
    try:
        await notice_service.create_system_notice(
            title=f"New material: {title}",
            body=f"New {source_type} uploaded for your course",
            notice_type="announcement",
            course_id=course_id,
            posted_by=current_user.id,
        )
    except Exception:
        pass

    return material


@router.get("/{course_id}/materials", response_model=list[MaterialResponse])
async def list_materials(
    course_id: str,
    topic_tag: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    return await classroom_service.list_materials(course_id, topic_tag)


@router.get("/{course_id}/materials/{material_id}/download")
async def download_material(
    course_id: str,
    material_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a download URL for a material file. Any enrolled user can download."""
    supabase = get_supabase_admin()
    # Get the material record
    result = (
        supabase.table("materials")
        .select("*")
        .eq("id", material_id)
        .eq("course_id", course_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Material not found")

    file_url = result.data.get("file_url", "")

    # Try to generate a signed URL from Supabase Storage
    try:
        bucket = "course-materials"
        storage_path = file_url.replace(f"{bucket}/", "")
        signed = supabase.storage.from_(bucket).create_signed_url(storage_path, 3600)
        return {"download_url": signed.get("signedURL") or signed.get("signedUrl", ""), "file_name": result.data.get("file_name")}
    except Exception:
        return {"download_url": "", "file_name": result.data.get("file_name"), "error": "File not available for download"}


# ─── Assignments ─────────────────────────────────────────────

@router.post("/{course_id}/assignments", response_model=AssignmentResponse)
async def create_assignment(
    course_id: str,
    data: AssignmentCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    try:
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
    except Exception as e:
        # Retry without optional fields that might not exist in DB
        result = await classroom_service.create_assignment(
            course_id=course_id,
            created_by=current_user.id,
            title=data.title,
            instructions=data.instructions,
            due_at=data.due_at.isoformat() if data.due_at else None,
            max_points=data.max_points,
        )

    # Auto-create scheduler event for assignment due date
    if data.due_at:
        try:
            from app.services import scheduler_service
            await scheduler_service.create_event(
                created_by=current_user.id,
                title=f"Due: {data.title}",
                event_type="assignment_due",
                start_at=data.due_at.isoformat(),
                end_at=data.due_at.isoformat(),
                course_id=course_id,
            )
        except Exception:
            pass  # Don't fail if scheduler event creation fails

    # Create notice
    try:
        await notice_service.create_system_notice(
            title=f"New assignment: {data.title}",
            body=data.instructions[:200] if data.instructions else "A new assignment has been posted",
            notice_type="assignment",
            course_id=course_id,
            posted_by=current_user.id,
        )
    except Exception:
        pass

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
        )

    return result

