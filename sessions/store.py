"""Session storage for chat history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import SESSIONS_DIR


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def delete_session(session_id: str) -> None:
    path = _session_path(session_id)
    if path.exists():
        path.unlink()


def read_session(session_id: str) -> list[dict[str, Any]]:
    path = _session_path(session_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def append_session_message(session_id: str, message: dict[str, Any]) -> None:
    path = _session_path(session_id)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = []
    data.append(message)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_sessions() -> list[dict[str, Any]]:
    if not SESSIONS_DIR.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in SESSIONS_DIR.glob("*.json"):
        stat = path.stat()
        items.append(
            {
                "session_id": path.stem,
                "updated_at": stat.st_mtime,
            }
        )
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return items

