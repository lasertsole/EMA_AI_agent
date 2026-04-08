"""Memory RAG index with incremental updates."""

from __future__ import annotations

import logging
from typing import Any, Optional

from config import MEMORY_DIR, MEMORY_INDEX_DIR, MEMORY_THRESHOLD

logger = logging.getLogger(__name__)


def _load_or_create_index() -> Optional[Any]:
    """Load existing memory index if available."""
    if MEMORY_INDEX_DIR.exists() and any(MEMORY_INDEX_DIR.iterdir()):
        try:
            from llama_index.core import StorageContext, load_index_from_storage

            storage_context = StorageContext.from_defaults(persist_dir=str(MEMORY_INDEX_DIR))
            return load_index_from_storage(storage_context)
        except ModuleNotFoundError:
            logger.warning("llama_index not installed, memory RAG disabled")
            return None
        except Exception:
            logger.exception("Failed to load memory index")
            return None
    return None


def _should_use_rag() -> bool:
    """Check if MEMORY.md exceeds threshold for RAG."""
    memory_file = MEMORY_DIR / "MEMORY.md"
    if not memory_file.exists():
        return False
    content = memory_file.read_text(encoding="utf-8")
    return len(content) >= MEMORY_THRESHOLD


async def update_memory_index_incremental(new_content: str) -> None:
    """Incrementally update memory index with new content."""
    if not new_content.strip():
        return

    try:
        from llama_index.core import Document, StorageContext, VectorStoreIndex
        from llama_index.core.node_parser import SentenceSplitter
    except ModuleNotFoundError:
        logger.warning("llama_index not installed, skip memory index update")
        return

    index = _load_or_create_index()
    doc = Document(
        text=new_content,
        metadata={"source": "MEMORY.md", "type": "memory_entry"},
    )

    splitter = SentenceSplitter(chunk_size=500, chunk_overlap=50)
    nodes = splitter.get_nodes_from_documents([doc])

    if index is None:
        index = VectorStoreIndex(nodes, storage_context=StorageContext.from_defaults())
        MEMORY_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(MEMORY_INDEX_DIR))
        logger.info("Created new memory index with %s nodes", len(nodes))
        return

    for node in nodes:
        index.insert(node)
    index.storage_context.persist(persist_dir=str(MEMORY_INDEX_DIR))
    logger.info("Updated memory index with %s new nodes", len(nodes))


def search_memory(query: str) -> str:
    """Search memory using RAG if available, else direct text."""
    if not _should_use_rag():
        memory_file = MEMORY_DIR / "MEMORY.md"
        if memory_file.exists():
            return memory_file.read_text(encoding="utf-8")
        return ""

    index = _load_or_create_index()
    if index is None:
        return ""

    engine = index.as_query_engine(similarity_top_k=5)
    response = engine.query(query)
    return str(response)
