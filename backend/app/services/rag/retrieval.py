"""
Academix AI — RAG Retrieval Service

Hybrid retrieval using Supabase pgvector (semantic) + metadata filters.
Calls the match_chunks() RPC function defined in the database migration.
"""

from typing import Optional

from app.config import get_settings
from app.database import get_supabase_admin
from app.services.rag.embeddings import generate_embedding
from app.models.rag import SourceChunk


async def retrieve_chunks(
    query: str,
    course_id: str,
    source_type: Optional[str] = None,
    exam_type: Optional[str] = None,
    topic_tag: Optional[str] = None,
    top_k: int = 10,
    threshold: float = 0.5,
) -> list[SourceChunk]:
    """
    Retrieve the most relevant content chunks for a query.
    
    Uses hybrid approach:
    1. Generate query embedding
    2. Call pgvector similarity search via match_chunks() RPC
    3. Apply metadata filters (course, source_type, exam_type, topic)
    
    Args:
        query: The search query text
        course_id: Filter by course
        source_type: Filter by 'notes', 'textbook', or 'pyq'
        exam_type: Filter by 'internal' or 'external'
        topic_tag: Filter by topic
        top_k: Number of results to return
        threshold: Minimum similarity threshold (0-1)
    
    Returns:
        List of SourceChunk objects with similarity scores
    """
    settings = get_settings()
    supabase = get_supabase_admin()

    # 1. Generate query embedding
    query_embedding = generate_embedding(query)

    # 2. Call the match_chunks RPC function
    result = supabase.rpc("match_chunks", {
        "query_embedding": query_embedding,
        "p_course_id": course_id,
        "p_source_type": source_type,
        "p_exam_type": exam_type,
        "p_topic_tag": topic_tag,
        "match_threshold": threshold,
        "match_count": top_k,
    }).execute()

    if not result.data:
        return []

    # 3. Enrich with document names
    doc_ids = list(set(r["document_id"] for r in result.data))
    doc_result = (
        supabase.table("content_documents")
        .select("id, file_name")
        .in_("id", doc_ids)
        .execute()
    )
    doc_names = {d["id"]: d["file_name"] for d in (doc_result.data or [])}

    # 4. Build SourceChunk responses
    chunks = []
    for row in result.data:
        chunks.append(SourceChunk(
            id=row["id"],
            text=row["text"],
            document_name=doc_names.get(row["document_id"], "Unknown"),
            page_ref=row.get("page_ref"),
            source_type=row["source_type"],
            similarity=row.get("similarity"),
        ))

    return chunks


async def retrieve_pyq_exemplars(
    course_id: str,
    exam_type: str,
    topic_tag: Optional[str] = None,
    count: int = 5,
) -> list[dict]:
    """
    Retrieve PYQ questions as style exemplars for Paper Style mode.
    These are used as pattern references (never copied verbatim).
    
    Returns raw PYQ question records for the style prompt.
    """
    supabase = get_supabase_admin()

    query = (
        supabase.table("pyq_questions")
        .select("*")
        .eq("course_id", course_id)
        .eq("exam_type", exam_type)
    )

    if topic_tag:
        query = query.eq("topic_tag", topic_tag)

    result = query.limit(count).execute()
    return result.data or []
