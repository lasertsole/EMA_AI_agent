"""Unified retrieval across Memory and Knowledge."""

from __future__ import annotations

import logging
from typing import Any

from config import KNOWLEDGE_DIR, KNOWLEDGE_INDEX_DIR
from .memory_index import _load_or_create_index, _should_use_rag, search_memory

logger = logging.getLogger(__name__)


def _load_knowledge_index() -> Any:
    """Load knowledge base index (including compressed sessions)."""
    try:
        from llama_index.core import (
            SimpleDirectoryReader,
            StorageContext,
            VectorStoreIndex,
            load_index_from_storage,
        )
    except ModuleNotFoundError:
        logger.warning("llama_index not installed, unified retrieval disabled")
        return None

    if not KNOWLEDGE_INDEX_DIR.exists() or not any(KNOWLEDGE_INDEX_DIR.iterdir()):
        docs = []
        if KNOWLEDGE_DIR.exists():
            docs = SimpleDirectoryReader(str(KNOWLEDGE_DIR)).load_data()
        index = VectorStoreIndex.from_documents(docs)
        KNOWLEDGE_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(KNOWLEDGE_INDEX_DIR))
        return index

    storage_context = StorageContext.from_defaults(persist_dir=str(KNOWLEDGE_INDEX_DIR))
    return load_index_from_storage(storage_context)


def _build_fusion_retriever() -> Any:
    """Build fusion retriever combining Memory and Knowledge."""
    try:
        from llama_index.core.retrievers import QueryFusionRetriever
    except ModuleNotFoundError:
        logger.warning("llama_index not installed, fallback to memory text retrieval")
        return None

    memory_retriever = None
    if _should_use_rag():
        memory_index = _load_or_create_index()
        if memory_index:
            memory_retriever = memory_index.as_retriever(similarity_top_k=5)

    knowledge_index = _load_knowledge_index()
    if knowledge_index is None:
        return None
    knowledge_retriever = knowledge_index.as_retriever(similarity_top_k=5)

    if memory_retriever:
        return QueryFusionRetriever(
            retrievers=[memory_retriever, knowledge_retriever],
            similarity_top_k=10,
        )
    return knowledge_retriever


def search_unified(query: str) -> str:
    """Unified search across Memory and Knowledge."""
    if not _should_use_rag():
        return search_memory(query)

    try:
        from llama_index.core.query_engine import RetrieverQueryEngine
    except ModuleNotFoundError:
        logger.warning("llama_index not installed, fallback to memory text retrieval")
        return search_memory(query)

    retriever = _build_fusion_retriever()
    if retriever is None:
        return search_memory(query)
    engine = RetrieverQueryEngine.from_args(retriever)
    response = engine.query(query)
    return str(response)
