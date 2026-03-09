"""Backend utility helpers."""

from __future__ import annotations

from pathlib import Path


def safe_join(root: Path, rel_path: str) -> Path:
    """Resolve rel_path under root and prevent path traversal."""
    candidate = (root / rel_path).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        raise ValueError("Path is خارج root_dir")
    return candidate

