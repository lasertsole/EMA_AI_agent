"""Session compression - compress old messages to structured summary."""

from __future__ import annotations

import json
import logging
from typing import Any
from pathlib import Path
from config import COMPRESS_RATIO
from models import simple_chat_model
from sessions.store import read_current_from_session
from config import ARCHIVE_THRESHOLD,  SESSIONS_DIR


logger = logging.getLogger(__name__)

compress_model = simple_chat_model

def _calculate_total_chars(messages: list[dict[str, Any]]) -> int:
    """Calculate total character count in sessions."""
    return sum(len(m.get("content", "")) for m in messages)


def _split_messages(
    messages: list[dict[str, Any]], ratio: float = COMPRESS_RATIO  # ratio 值越大，旧消息数组（要被压缩的部分）token占比就越大。
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split messages into old (to compress) and new (to keep)."""
    total_chars = _calculate_total_chars(messages)
    target_chars = total_chars * ratio

    compressed_chars = 0
    split_index = 0

    for i, msg in enumerate(messages):
        msg_chars = len(msg.get("content", ""))
        if compressed_chars + msg_chars > target_chars:
            break
        compressed_chars += msg_chars
        split_index = i + 1

    return messages[:split_index], messages[split_index:]

async def archive_session(session_id: str) -> None:
    """Compress old sessions messages to knowledge base."""
    messages = read_current_from_session(session_id)

    if _calculate_total_chars(messages) < ARCHIVE_THRESHOLD:
        return

    old_messages, new_messages = _split_messages(messages)
    if not old_messages:
        return

    tar_folder = Path(SESSIONS_DIR) / session_id

    # 确保目录存在
    tar_folder.parent.mkdir(parents=True, exist_ok=True)

    # 将要保留下来的新数据覆盖回current.jsonl
    current_path = tar_folder / "current.jsonl"
    current_path.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in new_messages) + "\n", encoding="utf-8")

    # 将要旧数据追加到history.jsonl
    history_path = tar_folder / "history.jsonl"
    with history_path.open("a", encoding="utf-8") as f:
        for m in old_messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
