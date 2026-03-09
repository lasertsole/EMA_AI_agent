"""Session storage for chat history."""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path
from config import SESSIONS_DIR

def _session_path(session_id: str) -> str:
    return (Path(SESSIONS_DIR) / f"{session_id}/L2.json").as_posix()


def delete_session(session_id: str) -> None:
    path = Path(_session_path(session_id))
    if path.exists():
        path.unlink()


def read_session(session_id: str) -> list[dict[str, Any]]:
    path = Path(_session_path(session_id))

    if not path.exists():
        return []

    # 如果文件存在但内容为空，则返回空列表
    if path.stat().st_size == 0:
        return []

    return json.loads(path.read_text(encoding="utf-8"))


def append_session_message(session_id: str, message: dict[str, Any]) -> None:
    path = Path(_session_path(session_id))

    # 总是先确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        if path.stat().st_size == 0:
            data = []
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = []

    data.append(message)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_sessions() -> list[dict[str, Any]]:
    if not SESSIONS_DIR.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in SESSIONS_DIR.glob("*/L2.json"):
        stat = path.stat()
        items.append(
            {
                "session_id": path.stem,
                "updated_at": stat.st_mtime,
            }
        )
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return items

