"""
Academix AI — Style Profile Service

Builds and updates Style Profiles from PYQ metadata.
A Style Profile captures the exam "style" for a course + exam type:
  - Total marks, duration
  - Section structure (e.g., "Section A: 5×2 marks MCQ")
  - Bloom's taxonomy level distribution
  - Recurring phrasing patterns
"""

import json
from typing import Optional
from collections import Counter

from app.database import get_supabase_admin


async def compute_style_profile(
    course_id: str,
    exam_type: str,
) -> Optional[dict]:
    """
    Compute or update a Style Profile for a course + exam type
    by analyzing all PYQ questions tagged for that combination.
    
    Returns the computed style profile dict, or None if insufficient data.
    """
    supabase = get_supabase_admin()

    # 1. Fetch all PYQ questions for this course + exam type
    result = (
        supabase.table("pyq_questions")
        .select("*")
        .eq("course_id", course_id)
        .eq("exam_type", exam_type)
        .execute()
    )

    questions = result.data or []
    if len(questions) < 3:
        # Not enough data for a meaningful style profile
        return None

    # 2. Analyze structure
    total_marks_per_paper = {}
    section_counts = Counter()
    bloom_counts = Counter()
    question_type_counts = Counter()
    marks_distribution = Counter()

    for q in questions:
        year = q.get("year", "unknown")
        marks = q.get("marks", 0)

        # Accumulate marks per year to estimate total
        if year not in total_marks_per_paper:
            total_marks_per_paper[year] = 0
        total_marks_per_paper[year] += marks

        # Count sections
        if q.get("section"):
            section_counts[q["section"]] += 1

        # Count Bloom's levels
        if q.get("bloom_level"):
            bloom_counts[q["bloom_level"]] += 1

        # Count question types
        if q.get("question_type"):
            question_type_counts[q["question_type"]] += 1

        # Marks distribution
        if marks:
            marks_distribution[marks] += 1

    # 3. Compute averages and distributions
    avg_total_marks = (
        sum(total_marks_per_paper.values()) // len(total_marks_per_paper)
        if total_marks_per_paper else None
    )

    total_bloom = sum(bloom_counts.values()) or 1
    bloom_distribution = {
        level: round(count / total_bloom, 2)
        for level, count in bloom_counts.items()
    }

    # Build section structure
    section_structure = []
    for section, count in sorted(section_counts.items()):
        # Find common marks value for this section
        section_questions = [q for q in questions if q.get("section") == section]
        section_marks = [q.get("marks", 0) for q in section_questions]
        common_marks = Counter(section_marks).most_common(1)[0][0] if section_marks else 0
        common_type = Counter(
            q.get("question_type", "unknown") for q in section_questions
        ).most_common(1)[0][0]

        section_structure.append({
            "section": section,
            "question_count": count,
            "marks_per_question": common_marks,
            "common_type": common_type,
        })

    # 4. Build the profile
    profile = {
        "total_marks": avg_total_marks,
        "section_structure": section_structure,
        "bloom_distribution": bloom_distribution,
        "common_patterns": {
            "question_types": dict(question_type_counts),
            "marks_distribution": dict(marks_distribution),
        },
        "question_count": len(questions),
        "confidence_score": min(1.0, len(questions) / 30),  # Full confidence at 30+ questions
        "pyq_count": len(set(q.get("document_id") for q in questions)),
    }

    # 5. Upsert into style_profiles table
    supabase.table("style_profiles").upsert({
        "course_id": course_id,
        "exam_type": exam_type,
        "total_marks": profile["total_marks"],
        "section_structure": profile["section_structure"],
        "bloom_distribution": profile["bloom_distribution"],
        "common_patterns": profile["common_patterns"],
        "question_count": profile["question_count"],
        "confidence_score": profile["confidence_score"],
        "pyq_count": profile["pyq_count"],
        "last_computed_at": "now()",
    }, on_conflict="course_id,exam_type").execute()

    return profile


async def get_style_profile(
    course_id: str,
    exam_type: str,
) -> Optional[dict]:
    """
    Get the current style profile for a course + exam type.
    Returns None if no profile exists yet.
    """
    supabase = get_supabase_admin()

    result = (
        supabase.table("style_profiles")
        .select("*")
        .eq("course_id", course_id)
        .eq("exam_type", exam_type)
        .single()
        .execute()
    )

    return result.data if result.data else None
