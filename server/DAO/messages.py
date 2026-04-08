import json
import shutil
from pathlib import Path
from typing import List, Any
from threading import Thread
from config import SESSIONS_DIR
from tasks.queue import task_queue
from langchain_core.messages import BaseMessage
from config import ARCHIVE_THRESHOLD, MEMORY_DIR


def _session_folder(session_id: str) -> str:
    return (Path(SESSIONS_DIR) / session_id).as_posix()

def _current_jsonl_path(session_id: str) -> str:
    return f"{_session_folder(session_id)}/current.jsonl"

def read_current_from_session(session_id: str) -> list[dict[str, Any]]:
    path: Path = Path(_current_jsonl_path(session_id))

    if not path.exists():
        return []

    # 如果文件存在但内容为空，则返回空列表
    if path.stat().st_size == 0:
        return []

    text_lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line.strip()) for line in text_lines if len(line) > 0]

def maybe_archive_history(session_id: str, all_messages: List[BaseMessage]) -> str | None:
    # 如果达到归档阈值，则归档历史会话
    total_chars = sum(len(getattr(m, "content", "")) for m in all_messages)
    if total_chars > ARCHIVE_THRESHOLD and task_queue:
        task_queue.archive_compress(session_id)
    return "ok"


"""以下是记忆抽取逻辑"""
def _append_memory(entry: str) -> None:
    path = MEMORY_DIR / "MEMORY.md"

    # 确保文件存在
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.write_text("# MEMORY\n", encoding="utf-8")
    content = path.read_text(encoding="utf-8").rstrip()
    updated = f"{content}\n\n{entry}\n"
    path.write_text(updated, encoding="utf-8")


def maybe_extract_memory(text: str) -> str | None:
    keywords = ["请记住", "记住这个", "记下来", "保存到记忆", "write to memory"]
    source = text.strip()

    memory_entry: str | None = None
    for kw in keywords:
        if kw in source:
            after = source.split(kw, 1)[1].strip()
            if after.startswith("：") or after.startswith(":"):
                after = after[1:].strip()
            memory_entry = after if after else source
            break

    if memory_entry:
        _append_memory(memory_entry)
        Thread(target=lambda: task_queue.enqueue_memory_index(memory_entry)).start()
"""以上是记忆抽取逻辑"""

def clear_session(session_id: str) -> None:
    """删除整个会话文件夹"""
    path = Path(_session_folder(session_id))
    if path.exists() and path.is_dir():
        shutil.rmtree(path)