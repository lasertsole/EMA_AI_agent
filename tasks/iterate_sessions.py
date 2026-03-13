"""Session compression - compress old messages to structured summary."""

from __future__ import annotations

import json
import logging
from typing import Any
from pathlib import Path
from tools import ALL_TOOLS
from config import ROOT_DIR
from models import base_model
from datetime import datetime
from sessions import append_timeline_entry


from config import (
    COMPRESS_THRESHOLD,
    SESSIONS_DIR,
)
from sessions.store import read_session

logger = logging.getLogger(__name__)


def _calculate_total_chars(messages: list[dict[str, Any]]) -> int:
    """Calculate total character count in session."""
    return sum(len(m.get("content", "")) for m in messages)


def _split_messages(
    messages: list[dict[str, Any]], ratio: float = 0.5  # ratio 值越大，旧消息数组（要被压缩的部分）就越大。
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


def _generate_summary(old_messages: list[dict[str, Any]]) -> str:
    """Generate structured summary from messages using LLM."""
    from langchain_core.prompts import ChatPromptTemplate
    llm = base_model

    conversation = "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in old_messages
    )

    prompt = ChatPromptTemplate.from_template(
        """Summarize the following conversation into a concise structured memo.

Conversation:
{conversation}

Output format:
# Session Summary {datetime}

## Topics
- Topic 1
- Topic 2

## Key Points
- Point 1
- Point 2

## Context
[Brief context and goals]
"""
    )
    prompt.partial_variables = {"datetime": datetime.now().strftime("%Y-%m-%d")}

    result = llm.invoke(prompt.format(conversation=conversation))
    content = result.content
    if isinstance(content, str):
        return content
    return str(content)


async def iterate_session(session_id: str) -> None:
    """iterate session messages."""
    messages = read_session(session_id)

    if _calculate_total_chars(messages) < COMPRESS_THRESHOLD:
        return

    old_messages, new_messages = _split_messages(messages)
    if not old_messages:
        return

    try:
        await append_timeline_entry(agent_dir = ROOT_DIR, session_id = session_id, tool_metas = [t["name"] for t in ALL_TOOLS])
    except Exception:
        logger.exception("Failed to summarize session %s", session_id)
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
