"""Session compression - compress old messages to structured summary."""

from __future__ import annotations

import json
import logging
from typing import Any
from pathlib import Path
from datetime import datetime
from config import COMPRESS_RATIO
from models import simple_chat_model
from sessions.store import read_session
from config import COMPRESS_THRESHOLD,  SESSIONS_DIR


logger = logging.getLogger(__name__)

compress_model = simple_chat_model.bind(temperature=0)

def _calculate_total_chars(messages: list[dict[str, Any]]) -> int:
    """Calculate total character count in session."""
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


def _generate_summary(old_messages: list[dict[str, Any]]) -> str:
    """Generate structured summary from messages using LLM."""
    from langchain_core.prompts import ChatPromptTemplate

    conversation = "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in old_messages
    )

    prompt = ChatPromptTemplate.from_template(
        """根据下面的对话内容编写简短、精确的摘要.

对话内容:
{conversation}

输出格式:
# 会话摘要 {datetime}

## 话题
- 话题 1
- 话题 2

## 关键点
- 关键点 1
- 关键点 2

## 上下文
[简短的上下文和目标]
"""
    )
    prompt.partial_variables = {"datetime": datetime.now().strftime("%Y-%m-%d")}

    result = compress_model.invoke(prompt.format(conversation=conversation))
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

    tar_folder = Path(SESSIONS_DIR) / session_id

    # 确保目录存在
    tar_folder.parent.mkdir(parents=True, exist_ok=True)

    summary_path = tar_folder / "summary.md"
    summary_path.write_text(
        f"""# Compressed Session: {session_id}

{summary}

---
*Compressed at: {datetime.now().isoformat()}*
""",
        encoding="utf-8",
    )

    # 将要保留下来的新数据覆盖回current.jsonl
    current_path = tar_folder / "current.jsonl"
    current_path.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in new_messages) + "\n", encoding="utf-8")

    # 将要旧数据追加到history.jsonl
    history_path = tar_folder / "history.jsonl"
    with history_path.open("a", encoding="utf-8") as f:
        for m in old_messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
