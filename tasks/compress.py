"""Session compression - compress old messages to structured summary."""

from __future__ import annotations

from models import base_model
from datetime import datetime
import json
import logging
from typing import Any

from config import (
    COMPRESS_THRESHOLD,
    COMPRESSED_SESSIONS_DIR,
    SESSIONS_DIR,
)
from sessions.store import read_session

logger = logging.getLogger(__name__)


def _calculate_total_chars(messages: list[dict[str, Any]]) -> int:
    """Calculate total character count in session."""
    return sum(len(m.get("content", "")) for m in messages)


def _split_messages(
    messages: list[dict[str, Any]], ratio: float = 0.5
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


async def compress_session(session_id: str) -> None:
    """Compress old session messages to knowledge base."""
    messages = read_session(session_id)

    if _calculate_total_chars(messages) < COMPRESS_THRESHOLD:
        return

    old_messages, new_messages = _split_messages(messages)
    if not old_messages:
        return

    try:
        summary = _generate_summary(old_messages)
    except Exception:
        logger.exception("Failed to summarize session %s", session_id)
        return

    COMPRESSED_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = COMPRESSED_SESSIONS_DIR / f"{session_id}.md"
    output_path.write_text(
        f"""# Compressed Session: {session_id}

{summary}

---
*Compressed at: {datetime.now().isoformat()}*
""",
        encoding="utf-8",
    )

    session_path = SESSIONS_DIR / f"{session_id}/L2.json"
    session_path.write_text(
        json.dumps(new_messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
