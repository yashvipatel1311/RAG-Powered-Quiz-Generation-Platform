"""
Academix AI — RAG Generation Service

Uses Groq API to generate quiz/exam questions grounded in retrieved content.
One engine, two modes: Quiz Generation (student) and Paper Style (teacher).
"""

import json
from typing import Optional

from app.config import get_settings
from app.models.rag import GenerationRequest, SourceChunk


def _build_quiz_prompt(
    request: GenerationRequest,
    context_chunks: list[SourceChunk],
    style_profile: Optional[dict] = None,
) -> str:
    """
    Build the LLM prompt for question generation.
    
    Key principles from PRD:
    - Retrieved content is the ONLY permitted factual source
    - Each question must cite which chunk(s) it came from
    - Quiz Generation: casual difficulty, instant answer key
    - Paper Style: strict adherence to Style Profile
    """
    # Format retrieved context
    context_text = ""
    for i, chunk in enumerate(context_chunks):
        context_text += f"\n--- Source {i+1} (ID: {chunk.id}) ---\n"
        context_text += f"From: {chunk.document_name or 'Unknown'}"
        if chunk.page_ref:
            context_text += f" | {chunk.page_ref}"
        context_text += f"\n{chunk.text}\n"

    # Determine question types string
    q_types = ", ".join(request.question_types)

    if request.mode == "paper_style" and style_profile:
        # Paper Style mode — strict format adherence
        style_info = json.dumps(style_profile, indent=2)
        prompt = f"""You are an exam paper generation assistant for an academic institution.

TASK: Generate {request.question_count} exam questions for a {request.exam_type or 'internal'} examination.

STYLE PROFILE (you MUST follow this format exactly):
{style_info}

ALLOWED QUESTION TYPES: {q_types}
DIFFICULTY: {request.difficulty}
TOPICS: {', '.join(request.topic_tags) if request.topic_tags else 'All topics from the source material'}

SOURCE MATERIAL (this is your ONLY permitted factual source — do NOT use any external knowledge):
{context_text}

CRITICAL RULES:
1. Every question MUST be answerable from the source material above.
2. Every question MUST cite which Source ID(s) it draws from.
3. The total marks MUST sum correctly according to the style profile.
4. Section structure MUST match the style profile.
5. Do NOT copy questions verbatim from any source — paraphrase and generate original questions.
6. Include Bloom's taxonomy level for each question.
7. For MCQ questions, provide exactly 4 options (A, B, C, D).

OUTPUT FORMAT: Return a valid JSON array of questions:
[
  {{
    "question_text": "...",
    "question_type": "mcq|short_answer|long_answer|true_false|fill_blank",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],  // only for MCQ
    "correct_answer": "...",
    "explanation": "Brief explanation of why this is correct",
    "marks": 2,
    "bloom_level": "remember|understand|apply|analyze|evaluate|create",
    "source_ids": ["source_id_1"],
    "section": "A"
  }}
]

Return ONLY the JSON array, no other text."""
    else:
        # Quiz Generation mode — more casual, student-friendly
        prompt = f"""You are a helpful quiz generator for students preparing for exams.

TASK: Generate {request.question_count} practice quiz questions.

QUESTION TYPES: {q_types}
DIFFICULTY: {request.difficulty}
TOPICS: {', '.join(request.topic_tags) if request.topic_tags else 'All topics from the source material'}

SOURCE MATERIAL (this is your ONLY factual source — do NOT use external knowledge):
{context_text}

RULES:
1. Every question MUST be answerable from the source material.
2. Cite which Source ID(s) each question draws from.
3. Make questions clear and educational — students should learn from taking this quiz.
4. Vary the difficulty within the {request.difficulty} range.
5. For MCQ, provide exactly 4 options with one correct answer.
6. Include a brief explanation for the correct answer.

OUTPUT FORMAT: Return a valid JSON array:
[
  {{
    "question_text": "...",
    "question_type": "mcq|short_answer|long_answer|true_false|fill_blank",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],  // only for MCQ
    "correct_answer": "...",
    "explanation": "Brief explanation",
    "marks": 1,
    "bloom_level": "remember|understand|apply|analyze|evaluate|create",
    "source_ids": ["source_id_1"]
  }}
]

Return ONLY the JSON array, no other text."""

    return prompt


async def generate_questions(
    request: GenerationRequest,
    context_chunks: list[SourceChunk],
    style_profile: Optional[dict] = None,
) -> list[dict]:
    """
    Generate questions using the Groq API.
    
    Args:
        request: Generation parameters
        context_chunks: Retrieved source chunks
        style_profile: Style profile for Paper Style mode (optional)
    
    Returns:
        List of generated question dicts
    """
    from groq import Groq

    settings = get_settings()

    # TODO: Your Groq API key is loaded from GROQ_API_KEY env variable
    client = Groq(api_key=settings.GROQ_API_KEY)

    prompt = _build_quiz_prompt(request, context_chunks, style_profile)

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert academic question generator. You ONLY generate questions grounded in the provided source material. You always return valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        
        # Parse the JSON response
        parsed = json.loads(content)
        
        # Handle both direct array and wrapped object responses
        if isinstance(parsed, list):
            questions = parsed
        elif isinstance(parsed, dict):
            # Try common wrapper keys
            for key in ["questions", "quiz", "data", "items"]:
                if key in parsed and isinstance(parsed[key], list):
                    questions = parsed[key]
                    break
            else:
                questions = [parsed] if "question_text" in parsed else []
        else:
            questions = []

        return questions

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse LLM response as JSON: {e}")
        # Try to extract JSON from the response
        import re
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return []
    except Exception as e:
        print(f"❌ Groq API error: {e}")
        raise
