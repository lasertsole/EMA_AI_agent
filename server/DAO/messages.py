from typing import List
from runtime import task_queue
from config import COMPRESS_THRESHOLD
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

def enqueue_append_timeline_entry(session_id: str, human_content:str, ai_content: str) -> str | None:
    # 添加viking L0 和 L1 索引
    task_queue.enqueue_append_timeline_entry(
    messages=[HumanMessage(content=human_content), AIMessage(content=ai_content)], session_id=session_id,
    tool_metas=[])

    return "ok"

def compress_history(session_id: str, all_messages: List[BaseMessage]) -> str | None:
    # 如果达到压缩阈值，则压缩历史会话
    total_chars = sum(len(getattr(m, "content", "")) for m in all_messages)
    if total_chars > COMPRESS_THRESHOLD and task_queue:
        task_queue.enqueue_compress(session_id)
    return "ok"