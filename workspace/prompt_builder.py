"""System prompt assembly."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from config import MEMORY_DIR, WORKSPACE_DIR
from skills.loader import get_skills_text
from workspace import CORE_FILE_NAMES

MAX_FILE_CHARS = 20_000


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) > MAX_FILE_CHARS:
        return text[:MAX_FILE_CHARS] + "\n...[truncated]"
    return text


def build_system_prompt(selected_file_names: Optional[List[str]] = None, selected_skill_names: Optional[List[str]] = None) -> str:
    skill_paths = get_skills_text(selected_skill_names)

    if selected_file_names is not None and len(selected_file_names) > 0:
        file_paths = [_read_text(WORKSPACE_DIR / f) for f in selected_file_names]
    else:
        file_paths = [
            *[_read_text(WORKSPACE_DIR / f) for f in CORE_FILE_NAMES],
            _read_text(MEMORY_DIR / "MEMORY.md"),
        ]

    parts = [*skill_paths, *file_paths]

    return "\n\n".join(p for p in parts if p)

