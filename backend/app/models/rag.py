"""
Academix AI — RAG Engine Models (Pydantic Schemas)

Covers: Content Documents, Generated Sets, Quiz Attempts, Style Profiles
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Content Document ---

class ContentDocumentResponse(BaseModel):
    id: str
    course_id: str
    uploaded_by: str
    file_url: str
    file_name: str
    file_size: Optional[int] = None
    source_type: str  # notes | textbook | pyq
    exam_type: Optional[str] = None
    year: Optional[int] = None
    status: str  # pending | processing | indexed | failed
    error_message: Optional[str] = None
    chunk_count: int = 0
    created_at: Optional[datetime] = None


# --- Quiz / Paper Generation Request ---

class GenerationRequest(BaseModel):
    """Request to generate a quiz (student) or paper draft (teacher)."""
    course_id: str
    mode: str  # 'quiz_generation' | 'paper_style'
    topic_tags: list[str] = []
    exam_type: Optional[str] = None  # 'internal' | 'external' (paper_style only)
    difficulty: str = "medium"  # 'easy' | 'medium' | 'hard'
    question_count: int = 10
    question_types: list[str] = ["mcq", "short_answer"]
    # MCQ options, short_answer, long_answer, true_false, fill_blank


class GeneratedSetResponse(BaseModel):
    id: str
    requested_by: str
    course_id: str
    mode: str
    exam_type: Optional[str] = None
    topic_tags: list[str] = []
    difficulty: str = "medium"
    status: str  # generating | draft | approved | rejected
    total_marks: Optional[int] = None
    total_questions: Optional[int] = None
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    # Joined
    course_name: Optional[str] = None
    questions: list["GeneratedQuestionResponse"] = []


class GeneratedQuestionResponse(BaseModel):
    id: str
    set_id: str
    question_text: str
    question_type: str
    options: Optional[list[str]] = None  # For MCQ
    correct_answer: str
    explanation: Optional[str] = None
    marks: int = 1
    bloom_level: Optional[str] = None
    source_chunk_ids: list[str] = []
    source_texts: list[str] = []  # Denormalized source text for display
    faithfulness_score: Optional[float] = None
    teacher_edited: bool = False
    question_order: int = 0


class QuestionEditRequest(BaseModel):
    """Teacher editing a generated question."""
    question_text: Optional[str] = None
    options: Optional[list[str]] = None
    correct_answer: Optional[str] = None
    marks: Optional[int] = None
    explanation: Optional[str] = None


class SetApprovalRequest(BaseModel):
    """Teacher approving/rejecting a generated set."""
    status: str  # 'approved' | 'rejected'


# --- Quiz Attempt (Student) ---

class QuizAttemptCreate(BaseModel):
    set_id: str


class QuizAnswerSubmit(BaseModel):
    """Submit answers for a quiz attempt."""
    answers: dict[str, str]  # {question_id: selected_answer}


class QuizAttemptResponse(BaseModel):
    id: str
    student_id: str
    set_id: str
    answers: dict = {}
    score: Optional[float] = None
    total_marks: Optional[int] = None
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    time_spent_seconds: Optional[int] = None
    status: str = "in_progress"
    # Joined
    questions: list[GeneratedQuestionResponse] = []


# --- Style Profile ---

class StyleProfileResponse(BaseModel):
    id: str
    course_id: str
    exam_type: str
    total_marks: Optional[int] = None
    duration_minutes: Optional[int] = None
    section_structure: list = []
    bloom_distribution: dict = {}
    common_patterns: dict = {}
    confidence_score: float = 0.0
    pyq_count: int = 0
    last_computed_at: Optional[datetime] = None


# --- RAG Source (for NotebookLM-style source panel) ---

class SourceChunk(BaseModel):
    """A source chunk displayed alongside generated questions."""
    id: str
    text: str
    document_name: Optional[str] = None
    page_ref: Optional[str] = None
    source_type: str
    similarity: Optional[float] = None


# Update forward refs
GeneratedSetResponse.model_rebuild()
