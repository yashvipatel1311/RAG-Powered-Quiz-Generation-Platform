"""
Academix AI — RAG Ingestion Pipeline

Handles: file download → text extraction → chunking → embedding → storage
Triggered as a BackgroundTask when materials are uploaded via Classroom.
"""

import re
from typing import Optional

from app.config import get_settings
from app.database import get_supabase_admin
from app.utils.file_parser import extract_text, get_page_ref
from app.services.rag.embeddings import generate_embeddings


def chunk_text(
    text: str,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> list[dict]:
    """
    Split text into semantically meaningful chunks.
    
    Strategy:
    1. Split on paragraph boundaries first
    2. Merge small paragraphs until chunk_size is reached
    3. Ensure overlap between chunks for context continuity
    
    Returns list of dicts: [{"text": ..., "chunk_index": ..., "page_ref": ...}]
    """
    settings = get_settings()
    chunk_size = settings.CHUNK_SIZE
    chunk_overlap = settings.CHUNK_OVERLAP

    # Split on double newlines (paragraph boundaries)
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = []
    current_length = 0
    chunk_index = 0

    for para in paragraphs:
        para_words = len(para.split())

        # If single paragraph exceeds chunk_size, split it further
        if para_words > chunk_size:
            # Flush current chunk first
            if current_chunk:
                chunk_text_str = "\n\n".join(current_chunk)
                chunks.append({
                    "text": chunk_text_str,
                    "chunk_index": chunk_index,
                    "token_count": len(chunk_text_str.split()),
                })
                chunk_index += 1
                current_chunk = []
                current_length = 0

            # Split large paragraph by sentences
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sentence in sentences:
                s_words = len(sentence.split())
                if current_length + s_words > chunk_size and current_chunk:
                    chunk_text_str = " ".join(current_chunk)
                    chunks.append({
                        "text": chunk_text_str,
                        "chunk_index": chunk_index,
                        "token_count": len(chunk_text_str.split()),
                    })
                    chunk_index += 1
                    # Keep overlap
                    overlap_text = " ".join(current_chunk[-2:]) if len(current_chunk) >= 2 else ""
                    current_chunk = [overlap_text] if overlap_text else []
                    current_length = len(overlap_text.split())
                current_chunk.append(sentence)
                current_length += s_words
        else:
            if current_length + para_words > chunk_size and current_chunk:
                chunk_text_str = "\n\n".join(current_chunk)
                chunks.append({
                    "text": chunk_text_str,
                    "chunk_index": chunk_index,
                    "token_count": len(chunk_text_str.split()),
                })
                chunk_index += 1
                # Keep last paragraph for overlap
                overlap = current_chunk[-1] if current_chunk else ""
                current_chunk = [overlap] if overlap else []
                current_length = len(overlap.split())

            current_chunk.append(para)
            current_length += para_words

    # Don't forget the last chunk
    if current_chunk:
        chunk_text_str = "\n\n".join(current_chunk)
        chunks.append({
            "text": chunk_text_str,
            "chunk_index": chunk_index,
            "token_count": len(chunk_text_str.split()),
        })

    return chunks


async def ingest_document(
    document_id: str,
    course_id: str,
    file_url: str,
    file_name: str,
    source_type: str,
    exam_type: Optional[str] = None,
):
    """
    Full ingestion pipeline for a single document.
    
    Called as a BackgroundTask after file upload.
    
    Pipeline:
    1. Download file from Supabase Storage
    2. Extract text (PDF/DOCX/PPTX/TXT)
    3. Chunk text into ~400-token segments
    4. Generate embeddings for all chunks (batch)
    5. Store chunks + embeddings in content_chunks table
    6. Update document status to 'indexed'
    """
    supabase = get_supabase_admin()

    try:
        # Update status to processing
        supabase.table("content_documents").update({
            "status": "processing"
        }).eq("id", document_id).execute()

        # 1. Download file from Supabase Storage
        # Determine bucket based on source_type
        bucket = "pyq-papers" if source_type == "pyq" else "course-materials"
        
        # Extract storage path from file_url
        # file_url format: {bucket}/{path}
        storage_path = file_url
        if "/" in file_url:
            parts = file_url.split("/", 1)
            if parts[0] in ("course-materials", "pyq-papers", "submissions"):
                storage_path = parts[1]
                bucket = parts[0]

        file_bytes = supabase.storage.from_(bucket).download(storage_path)

        # 2. Extract text
        text = extract_text(file_bytes, file_name)
        if not text or len(text.strip()) < 50:
            raise ValueError("Extracted text is too short or empty")

        # 3. Chunk text
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No chunks produced from text")

        # 4. Generate embeddings (batch)
        chunk_texts = [c["text"] for c in chunks]
        embeddings = generate_embeddings(chunk_texts)

        # 5. Store chunks with embeddings
        chunk_records = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Find page reference
            page_ref = get_page_ref(text, text.find(chunk["text"][:50]))

            chunk_records.append({
                "document_id": document_id,
                "course_id": course_id,
                "text": chunk["text"],
                "source_type": source_type,
                "exam_type": exam_type,
                "chunk_index": chunk["chunk_index"],
                "token_count": chunk.get("token_count"),
                "page_ref": page_ref,
                "embedding": embedding,
            })

        # Insert in batches of 50
        for batch_start in range(0, len(chunk_records), 50):
            batch = chunk_records[batch_start:batch_start + 50]
            supabase.table("content_chunks").insert(batch).execute()

        # 6. Update document status
        supabase.table("content_documents").update({
            "status": "indexed",
            "chunk_count": len(chunks),
        }).eq("id", document_id).execute()

        print(f"✅ Ingested document {document_id}: {len(chunks)} chunks created")

    except Exception as e:
        # Mark as failed with error message
        supabase.table("content_documents").update({
            "status": "failed",
            "error_message": str(e)[:500],
        }).eq("id", document_id).execute()
        print(f"❌ Ingestion failed for document {document_id}: {e}")
        raise
