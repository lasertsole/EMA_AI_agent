"""System prompt assembly."""

from __future__ import annotations

from pathlib import Path

from config import MEMORY_DIR, WORKSPACE_DIR
from skills.loader import get_skills_text


MAX_FILE_CHARS = 20_000


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) > MAX_FILE_CHARS:
        return text[:MAX_FILE_CHARS] + "\n...[truncated]"
    return text


def build_system_prompt() -> str:
    parts = [
        get_skills_text(),
        _read_text(WORKSPACE_DIR / "SOUL.md"),
        _read_text(WORKSPACE_DIR / "IDENTITY.md"),
        _read_text(WORKSPACE_DIR / "USER.md"),
        _read_text(WORKSPACE_DIR / "AGENTS.md"),
        _read_text(MEMORY_DIR / "MEMORY.md"),
    ]
    return "\n\n".join(p for p in parts if p)

