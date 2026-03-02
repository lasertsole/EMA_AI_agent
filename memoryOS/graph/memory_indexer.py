"""MemoryIndexer - Vector index for MEMORY.md with auto-rebuild on change."""

import hashlib
from pathlib import Path
from typing import Any
from models import embed_model

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

    def _get_file_hash(self) -> str:
        """Get MD5 hash of MEMORY.md."""
        if not self._memory_path.exists():
            return ""
        content = self._memory_path.read_bytes()
        return  hashlib.md5(content).hexdigest()

    def _save_file_hash(self, hash_value: str) -> None:
        """Save the current hash."""
        self._hash_path.parent.mkdir(parents = True, exist_ok = True)
        self._hash_path.write_text(hash_value, encoding="utf-8")

    def _maybe_rebuild(self) -> None:
        """Rebuild the index if MEMORY.md has changed."""
        current_hash = self._get_file_hash()
        stored_hash = self._get_stored_hash()
        if current_hash and current_hash != stored_hash:
            self.rebuild_index()

    def rebuild_index(self) -> None:
        """Rebuild MEMORY.md, split into chunks, build vector index, persist."""
        if not self._memory_path.exists():
            print("memory/MEMORY.md not found, skipping index build")
            self._index = None
            return
        try:
            from llama_index.core import (
                Document,
                StorageContext,
                VectorStoreIndex,
            )
            from llama_index.core.node_parser import SentenceSplitter
            from llama_index.core.settings import Settings

            Settings.embed_model = embed_model

            content = self._memory_path.read_text(encoding = "utf-8")
            if not content.strip():
                self._index = None
                return

            doc = Document(text = content, metadata={"source": "MEMORY.md"})

            splitter = SentenceSplitter(chunk_size=256, chunk_overlap=32)
            nodes = splitter.get_nodes_from_documents([doc])

            self._storage_dir.mkdir(parents = True, exist_ok = True)
            index = VectorStoreIndex(nodes)
            index.storage_context.persist(persist_dir=str(self._storage_dir))
            self._index = index

            # Save hash (TODO _save_hash 尚未创建)
            self._save_hash(self._get_file_hash())
            print(f"Memory index rebuilt: ({len(nodes)}  chunks)")

        except ImportError as e:
            print(f"LlamaIndex not fully installed: {e}")
            self._index = None
        except Exception as e:
            print(f"Memory index build error: {e}")
            self._index = None