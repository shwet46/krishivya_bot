"""RAG compatibility module with optional Pinecone retrieval.

LLM processing logic primarily lives in llm_processing/llm_service.py.
RAG retrieval is intentionally paused by default and can be enabled with env vars.
"""

from __future__ import annotations

import os
from typing import Any

from llm_processing import llm_service
from llm_processing.llm_service import WELCOME_MESSAGE, parse_reminder_request

# Keep RAG paused unless explicitly enabled.
RAG_PROCESSING_PAUSED = os.getenv("RAG_PROCESSING_PAUSED", "true").lower() == "true"
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "agriculture")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))


def _pinecone_index() -> Any | None:
    """Create a Pinecone index handle if config is available."""
    if RAG_PROCESSING_PAUSED:
        return None
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        return None

    try:
        from pinecone import Pinecone
    except Exception as exc:
        print(f"[RAG] Pinecone SDK unavailable: {exc}")
        return None

    try:
        client = Pinecone(api_key=PINECONE_API_KEY)
        return client.Index(PINECONE_INDEX_NAME)
    except Exception as exc:
        print(f"[RAG] Failed to initialize Pinecone index: {exc}")
        return None


def query_pinecone_context(user_input: str, query_vector: list[float] | None = None) -> list[str]:
    """Return top context chunks from Pinecone for the user query.

    RAG is paused by default. Also, this function expects a precomputed embedding
    vector for now and does not generate embeddings internally yet.
    """
    if RAG_PROCESSING_PAUSED:
        return []
    if not user_input.strip() or not query_vector:
        return []

    index = _pinecone_index()
    if index is None:
        return []

    try:
        result = index.query(
            vector=query_vector,
            top_k=RAG_TOP_K,
            include_metadata=True,
            namespace=PINECONE_NAMESPACE,
        )
    except Exception as exc:
        print(f"[RAG] Pinecone query failed: {exc}")
        return []

    chunks: list[str] = []
    for match in (result.get("matches") or []):
        metadata = match.get("metadata") or {}
        chunk = metadata.get("text") or metadata.get("chunk") or metadata.get("content")
        if chunk:
            chunks.append(str(chunk).strip())
    return [c for c in chunks if c]


def _build_rag_context(chunks: list[str]) -> str:
    if not chunks:
        return ""
    lines = [f"[{i}] {chunk}" for i, chunk in enumerate(chunks, start=1)]
    return "\n".join(lines)


def generate_response(
    user_input: str,
    image_bytes: bytes | None = None,
    query_vector: list[float] | None = None,
) -> str:
    """Generate response with optional Pinecone context when RAG is enabled."""
    if image_bytes:
        return llm_service.generate_response(user_input, image_bytes=image_bytes)

    rag_chunks = query_pinecone_context(user_input=user_input, query_vector=query_vector)
    if not rag_chunks:
        return llm_service.generate_response(user_input)

    rag_context = _build_rag_context(rag_chunks)
    prompt = (
        "Use the retrieved agriculture context below if relevant. "
        "If context is not relevant, ignore it and answer normally.\n\n"
        f"Retrieved context:\n{rag_context}\n\n"
        f"User question:\n{user_input}"
    )

    try:
        return llm_service._call_sarvam(
            [
                {"role": "system", "content": llm_service.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
    except Exception:
        return llm_service.generate_response(user_input)


__all__ = [
    "WELCOME_MESSAGE",
    "generate_response",
    "parse_reminder_request",
    "query_pinecone_context",
    "RAG_PROCESSING_PAUSED",
]
