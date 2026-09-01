"""
Academix AI — RAG Verification Service

Post-generation quality checks:
1. Faithfulness check — is each question actually supported by its cited chunks?
2. Answer-drift check — does the marked correct answer match the source material?

Both checks use a second LLM pass via Groq.
"""

import json
from typing import Optional

from app.config import get_settings
from app.models.rag import SourceChunk


async def verify_faithfulness(
    question_text: str,
    correct_answer: str,
    source_texts: list[str],
) -> dict:
    """
    Verify that a generated question + answer is faithful to its source material.
    
    Returns:
        {
            "is_faithful": bool,
            "score": float (0-1),
            "reason": str
        }
    """
    from groq import Groq
    settings = get_settings()
    client = Groq(api_key=settings.GROQ_API_KEY)

    sources_combined = "\n---\n".join(source_texts)

    prompt = f"""You are a quality verification assistant. Your job is to verify whether a generated exam question and its answer are faithfully grounded in the provided source material.

QUESTION: {question_text}
CORRECT ANSWER: {correct_answer}

SOURCE MATERIAL:
{sources_combined}

VERIFICATION TASKS:
1. Is the question answerable from the source material? (not from external knowledge)
2. Is the marked correct answer actually supported by the source material?
3. Are there any factual errors or hallucinations?

Return a JSON object:
{{
    "is_faithful": true/false,
    "faithfulness_score": 0.0 to 1.0,
    "answer_matches_source": true/false,
    "reason": "Brief explanation"
}}

Return ONLY the JSON object."""

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise verification assistant. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # Low temperature for consistency
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        return {
            "is_faithful": result.get("is_faithful", False),
            "score": result.get("faithfulness_score", 0.0),
            "answer_matches": result.get("answer_matches_source", False),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        print(f"⚠️  Faithfulness check failed: {e}")
        # Default to passing if verification fails (don't block generation)
        return {
            "is_faithful": True,
            "score": 0.5,
            "answer_matches": True,
            "reason": f"Verification skipped due to error: {str(e)}",
        }


async def verify_question_set(
    questions: list[dict],
    source_chunks: list[SourceChunk],
) -> list[dict]:
    """
    Verify an entire set of generated questions.
    
    For each question:
    1. Look up its cited source chunks
    2. Run faithfulness + answer-drift check
    3. Attach verification score
    4. Filter out unfaithful questions
    
    Returns only questions that pass verification.
    """
    # Build a lookup of chunk IDs to texts
    chunk_lookup = {chunk.id: chunk.text for chunk in source_chunks}

    verified_questions = []
    for q in questions:
        # Get source texts for this question
        source_ids = q.get("source_ids", [])
        source_texts = [
            chunk_lookup[sid] for sid in source_ids
            if sid in chunk_lookup
        ]

        # If no source texts found, use all context (fallback)
        if not source_texts:
            source_texts = [chunk.text for chunk in source_chunks[:3]]

        # Run verification
        result = await verify_faithfulness(
            question_text=q.get("question_text", ""),
            correct_answer=q.get("correct_answer", ""),
            source_texts=source_texts,
        )

        q["faithfulness_score"] = result["score"]

        # Only include questions that pass verification
        if result["is_faithful"] and result["answer_matches"]:
            verified_questions.append(q)
        else:
            print(f"⚠️  Filtered out unfaithful question: {q.get('question_text', '')[:50]}...")
            print(f"   Reason: {result['reason']}")

    return verified_questions
