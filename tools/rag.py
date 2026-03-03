"""RAG tool facade (delegates to unified retrieval)."""

from __future__ import annotations

from tasks.unified_retrieval import search_unified


def search_knowledge_base(query: str) -> str:
    return search_unified(query)
