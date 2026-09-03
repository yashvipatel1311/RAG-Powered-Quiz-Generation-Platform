"""
Academix AI — RAG Engine Router

The core AI feature — Quiz Generation (Student) + Paper Style (Teacher).
One underlying engine, two modes.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import Optional

from app.dependencies import get_current_user, require_role, CurrentUser
from app.models.rag import (
    GenerationRequest, GeneratedSetResponse, GeneratedQuestionResponse,
    QuestionEditRequest, SetApprovalRequest,
    QuizAttemptCreate, QuizAnswerSubmit, QuizAttemptResponse,
    ContentDocumentResponse, StyleProfileResponse,
)
from app.services.rag import retrieval, generation, verification, style_profile
from app.services import notice_service
from app.database import get_supabase_admin

router = APIRouter()


# ─── Quiz / Paper Generation ────────────────────────────────

@router.post("/generate", response_model=GeneratedSetResponse)
async def generate_quiz(
    data: GenerationRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Generate a quiz (student) or paper draft (teacher).
    
    This is the core RAG pipeline:
    1. Retrieve relevant content chunks
    2. (Paper Style) Load style profile
    3. Generate questions via Groq
    4. Verify faithfulness
    5. Store and return results
    """
    supabase = get_supabase_admin()

    # Access control: students can only use quiz_generation mode
    if current_user.role == "student" and data.mode == "paper_style":
        raise HTTPException(status_code=403, detail="Students cannot access Paper Style")

    # 1. Retrieve relevant chunks
    query_text = " ".join(data.topic_tags) if data.topic_tags else data.mode
    chunks = await retrieval.retrieve_chunks(
        query=query_text,
        course_id=data.course_id,
        source_type=None,  # Search all source types
        exam_type=data.exam_type,
        top_k=15,
    )

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No indexed content found for this course. Please upload materials first.",
        )

    # 2. Load style profile (Paper Style only)
    style = None
    if data.mode == "paper_style" and data.exam_type:
        style = await style_profile.get_style_profile(data.course_id, data.exam_type)

    # 3. Create the generated set record (status: generating)
    set_result = supabase.table("generated_sets").insert({
        "requested_by": current_user.id,
        "course_id": data.course_id,
        "mode": data.mode,
        "exam_type": data.exam_type,
        "topic_tags": data.topic_tags,
        "difficulty": data.difficulty,
        "status": "generating",
        "total_questions": data.question_count,
        "generation_config": {
            "question_types": data.question_types,
            "difficulty": data.difficulty,
        },
    }).execute()
    set_id = set_result.data[0]["id"]

    try:
        # 4. Generate questions via Groq
        raw_questions = await generation.generate_questions(data, chunks, style)

        if not raw_questions:
            supabase.table("generated_sets").update({"status": "draft", "total_questions": 0}).eq("id", set_id).execute()
            raise HTTPException(status_code=500, detail="Failed to generate questions")

        # 5. Verify faithfulness (optional — can be slow for large sets)
        verified_questions = raw_questions
        if len(raw_questions) <= 15:  # Only verify for reasonable set sizes
            try:
                verified_questions = await verification.verify_question_set(raw_questions, chunks)
            except Exception as e:
                print(f"⚠️ Verification skipped: {e}")
                verified_questions = raw_questions

        # 6. Store generated questions
        total_marks = 0
        for i, q in enumerate(verified_questions):
            marks = q.get("marks", 1)
            total_marks += marks

            # Map source IDs to chunk texts for display
            source_ids = q.get("source_ids", [])
            source_texts = [
                c.text[:200] for c in chunks if c.id in source_ids
            ][:3]  # Max 3 sources per question

            supabase.table("generated_questions").insert({
                "set_id": set_id,
                "question_text": q.get("question_text", ""),
                "question_type": q.get("question_type", "mcq"),
                "options": q.get("options"),
                "correct_answer": q.get("correct_answer", ""),
                "explanation": q.get("explanation"),
                "marks": marks,
                "bloom_level": q.get("bloom_level"),
                "source_chunk_ids": source_ids,
                "source_texts": source_texts if source_texts else [c.text[:200] for c in chunks[:2]],
                "faithfulness_score": q.get("faithfulness_score"),
                "question_order": i + 1,
            }).execute()

        # 7. Update set status
        status = "draft" if data.mode == "paper_style" else "draft"
        supabase.table("generated_sets").update({
            "status": status,
            "total_questions": len(verified_questions),
            "total_marks": total_marks,
        }).eq("id", set_id).execute()

    except HTTPException:
        raise
    except Exception as e:
        supabase.table("generated_sets").update({
            "status": "draft", "total_questions": 0
        }).eq("id", set_id).execute()
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

    # 8. Fetch and return the complete set
    return await _get_set_with_questions(set_id)


@router.get("/sets", response_model=list[GeneratedSetResponse])
async def list_generated_sets(
    course_id: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List generated sets for the current user."""
    supabase = get_supabase_admin()
    query = (
        supabase.table("generated_sets")
        .select("*, courses(name)")
        .eq("requested_by", current_user.id)
        .order("created_at", desc=True)
    )
    if course_id:
        query = query.eq("course_id", course_id)
    if mode:
        query = query.eq("mode", mode)

    result = query.execute()
    sets = result.data or []
    for s in sets:
        if s.get("courses"):
            s["course_name"] = s["courses"]["name"]
            del s["courses"]
    return sets


@router.get("/sets/{set_id}", response_model=GeneratedSetResponse)
async def get_generated_set(
    set_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a generated set with all its questions."""
    return await _get_set_with_questions(set_id)


# ─── Paper Style: Edit & Approve ─────────────────────────────

@router.patch("/sets/{set_id}/questions/{question_id}", response_model=GeneratedQuestionResponse)
async def edit_question(
    set_id: str,
    question_id: str,
    data: QuestionEditRequest,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """Edit a generated question (teacher only, Paper Style)."""
    supabase = get_supabase_admin()
    updates = data.model_dump(exclude_none=True)
    updates["teacher_edited"] = True
    result = supabase.table("generated_questions").update(updates).eq("id", question_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Question not found")
    return result.data[0]


@router.post("/sets/{set_id}/approve", response_model=GeneratedSetResponse)
async def approve_set(
    set_id: str,
    data: SetApprovalRequest,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """Approve or reject a Paper Style generated set (teacher only)."""
    supabase = get_supabase_admin()

    updates = {"status": data.status}
    if data.status == "approved":
        updates["approved_by"] = current_user.id
        updates["approved_at"] = "now()"

    supabase.table("generated_sets").update(updates).eq("id", set_id).execute()

    # Create audit notice
    await notice_service.create_system_notice(
        title=f"Paper Style set {data.status}",
        body=f"A generated paper draft has been {data.status} by {current_user.full_name}",
        notice_type="admin",
        posted_by=current_user.id,
    )

    return await _get_set_with_questions(set_id)


@router.delete("/sets/{set_id}/questions/{question_id}")
async def delete_question(
    set_id: str,
    question_id: str,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """Delete a question from a generated set (teacher only)."""
    supabase = get_supabase_admin()
    supabase.table("generated_questions").delete().eq("id", question_id).execute()
    return {"message": "Question deleted"}


# ─── Quiz Attempts (Student) ────────────────────────────────

@router.post("/attempts", response_model=QuizAttemptResponse)
async def start_quiz_attempt(
    data: QuizAttemptCreate,
    current_user: CurrentUser = Depends(require_role("student")),
):
    """Start a new quiz attempt (student only)."""
    supabase = get_supabase_admin()
    result = supabase.table("student_quiz_attempts").insert({
        "student_id": current_user.id,
        "set_id": data.set_id,
        "status": "in_progress",
    }).execute()

    attempt = result.data[0]
    # Fetch questions
    questions = (
        supabase.table("generated_questions")
        .select("*")
        .eq("set_id", data.set_id)
        .order("question_order")
        .execute()
    )
    attempt["questions"] = questions.data or []
    return attempt


@router.post("/attempts/{attempt_id}/submit", response_model=QuizAttemptResponse)
async def submit_quiz_attempt(
    attempt_id: str,
    data: QuizAnswerSubmit,
    current_user: CurrentUser = Depends(require_role("student")),
):
    """Submit answers for a quiz attempt and auto-grade."""
    supabase = get_supabase_admin()

    # Get attempt
    attempt = (
        supabase.table("student_quiz_attempts")
        .select("*")
        .eq("id", attempt_id)
        .eq("student_id", current_user.id)
        .single()
        .execute()
    )
    if not attempt.data:
        raise HTTPException(status_code=404, detail="Attempt not found")

    # Get questions for auto-grading
    questions = (
        supabase.table("generated_questions")
        .select("*")
        .eq("set_id", attempt.data["set_id"])
        .order("question_order")
        .execute()
    )

    # Auto-grade objective questions
    score = 0
    total_marks = 0
    for q in (questions.data or []):
        total_marks += q.get("marks", 1)
        student_answer = data.answers.get(q["id"], "").strip().lower()
        correct_answer = q.get("correct_answer", "").strip().lower()

        if q["question_type"] in ("mcq", "true_false"):
            if student_answer == correct_answer:
                score += q.get("marks", 1)
        elif q["question_type"] == "fill_blank":
            if student_answer == correct_answer:
                score += q.get("marks", 1)
        # For short_answer and long_answer: self-assessed by student (score not auto-calculated)

    # Update attempt
    from datetime import datetime, timezone
    result = supabase.table("student_quiz_attempts").update({
        "answers": data.answers,
        "score": score,
        "total_marks": total_marks,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "submitted",
    }).eq("id", attempt_id).execute()

    attempt_data = result.data[0]
    attempt_data["questions"] = questions.data or []
    return attempt_data


@router.get("/attempts", response_model=list[QuizAttemptResponse])
async def list_quiz_attempts(
    course_id: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List quiz attempts for the current student."""
    supabase = get_supabase_admin()
    query = (
        supabase.table("student_quiz_attempts")
        .select("*, generated_sets(course_id, mode, topic_tags)")
        .eq("student_id", current_user.id)
        .order("started_at", desc=True)
    )

    result = query.execute()
    return result.data or []


# ─── Content Documents Status ────────────────────────────────

@router.get("/documents/{course_id}", response_model=list[ContentDocumentResponse])
async def list_content_documents(
    course_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List content documents and their ingestion status for a course."""
    supabase = get_supabase_admin()
    result = (
        supabase.table("content_documents")
        .select("*")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


# ─── Style Profiles ──────────────────────────────────────────

@router.get("/style-profile/{course_id}/{exam_type}", response_model=StyleProfileResponse)
async def get_style_profile(
    course_id: str,
    exam_type: str,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """Get the style profile for a course + exam type (teacher only)."""
    result = await style_profile.get_style_profile(course_id, exam_type)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No style profile found. Upload more PYQ papers to generate one.",
        )
    return result


@router.post("/style-profile/{course_id}/{exam_type}/recompute", response_model=StyleProfileResponse)
async def recompute_style_profile(
    course_id: str,
    exam_type: str,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """Recompute the style profile from current PYQ data."""
    result = await style_profile.compute_style_profile(course_id, exam_type)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Not enough PYQ data to compute a style profile (need at least 3 questions).",
        )
    return result


# ─── Helper ──────────────────────────────────────────────────

async def _get_set_with_questions(set_id: str) -> dict:
    """Fetch a generated set with all its questions."""
    supabase = get_supabase_admin()

    set_data = (
        supabase.table("generated_sets")
        .select("*, courses(name)")
        .eq("id", set_id)
        .single()
        .execute()
    )
    if not set_data.data:
        raise HTTPException(status_code=404, detail="Generated set not found")

    result = set_data.data
    if result.get("courses"):
        result["course_name"] = result["courses"]["name"]
        del result["courses"]

    # Fetch questions
    questions = (
        supabase.table("generated_questions")
        .select("*")
        .eq("set_id", set_id)
        .order("question_order")
        .execute()
    )
    result["questions"] = questions.data or []

    return result
