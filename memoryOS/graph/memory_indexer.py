"""MemoryIndexer - Vector index for MEMORY.md with auto-rebuild on change."""

import hashlib
import os
from pathlib import Path
from typing import Any


class MemoryIndexer:
    """Indexes memory/MEMORY.md for RAG retrieval.

    Uses MD5 hash to detect changes and auto-rebuild the vector index.
    Storage is kept separate from knowledge base index.
    """

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._memory_path = base_dir / "memory" / "MEMORY.md"
        self._storage_dir = base_dir / "storage" / "memory_index"
        self._hash_path = self._storage_dir / ".memory_hash"
        self._index: Any = None