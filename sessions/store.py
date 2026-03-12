"""Session storage for chat history."""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path
from config import SESSIONS_DIR

def _session_path(session_id: str) -> str:
    return (Path(SESSIONS_DIR) / f"{session_id}/current.jsonl").as_posix()


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

    text_lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line.strip()) for line in text_lines if len(line) > 0]


def append_session_message(session_id: str, message: dict[str, Any]) -> None:
    if not isinstance(message["role"], str) or not isinstance(message["content"], str) or not isinstance(message["timestamp"], str):
        raise ValueError("Invalid message")

    path = Path(_session_path(session_id))

    # 总是先确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")