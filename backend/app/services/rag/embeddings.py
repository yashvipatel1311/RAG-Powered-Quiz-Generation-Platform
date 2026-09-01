"""
Academix AI — Embedding Model Wrapper

Provides a singleton sentence-transformers model for generating embeddings.
Uses all-MiniLM-L6-v2 (384 dimensions) by default.
"""

from functools import lru_cache
from typing import Union
import numpy as np

from app.config import get_settings


@lru_cache()
def get_embedding_model():
    """
    Load and cache the sentence-transformers model.
    Model is downloaded automatically on first use (~80MB).
    """
    from sentence_transformers import SentenceTransformer
    settings = get_settings()
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return model


def generate_embedding(text: str) -> list[float]:
    """
    Generate an embedding vector for a single text string.
    
    Args:
        text: The text to embed
        
    Returns:
        A list of floats (384 dimensions for all-MiniLM-L6-v2)
    """
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embedding vectors for a batch of texts.
    More efficient than calling generate_embedding() in a loop.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors
    """
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()
