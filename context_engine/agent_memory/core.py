import sqlite3
from .type import Turn
from pydantic import BaseModel, Field
from .store import (get_db, add_turn as db_add_history, get_turns, get_turns_by_lastest_n, get_turns_count_by_session_id,
                    fetch_and_delete_earliest_turns_by_session_id, add_rag, retrieve_rag)

_db: sqlite3.Connection = get_db()

def add_history(session_id: str, user_text: str, ai_text: str)-> None:
    turn_text: str = f"{user_text}\n\n{ai_text.replace('\n', ' ').replace('\r', '')}"

    db_add_history(
        db= _db,
        session_id= session_id,
        turn_text= turn_text
    )

    need_to_lightrag:list[Turn] = []

    # 删除多余的历史记录
    turn_counts = get_turns_count_by_session_id(_db, session_id)
    while turn_counts >= 10:
        need_to_lightrag = fetch_and_delete_earliest_turns_by_session_id(_db, session_id)

    # 向图谱中添加数据
    if len(need_to_lightrag)>0:
        add_rag(session_id, [r.turn_text for r in need_to_lightrag])

class TimeLimited(BaseModel):
    time_start: str | None = Field(default=None, description="起始时间，格式：YYYYMMDDHHmmss", examples= ["20260411154119"])
    time_end: str | None = Field(default=None, description="结束时间，格式：YYYYMMDDHHmmss", examples= ["20260411154119"])

async def retrieve_history_prompt(session_id: str, user_text: str) -> str:
    retrieve_turns: list[Turn] = get_turns(
        db=_db,
        session_id=session_id,
        query=user_text,
        limit=5,
    )

    turns_of_history: str = f"{'\n\n'.join(['<turn>\n'+h.turn_text+'\n</turn>' for h in retrieve_turns])}"

    rag: str = await retrieve_rag(session_id=session_id, query_text=user_text)

    return (
        "===== 以下是 agent-memory 根据用户输入的内容 匹配到的 历史对话记录 =====\n\n"
        f"{turns_of_history}"
        "\n\n===== 以下是 agent-memory 根据用户输入的内容 匹配到的 历史对话记录 ====="""
        "\n\n===== 以下是 agent-memory 根据用户输入的内容 匹配到的 rag =====\n\n"
        f"{rag}"
        "\n\n===== 以下是 agent-memory 根据用户输入的内容 匹配到的 rag ====="""
    )

def retrieve_history_by_last_n_prompt(session_id: str, n: int = 5) -> str:
    retrieve_turns: list[Turn] = get_turns_by_lastest_n(
        db=_db,
        session_id=session_id,
        last_n=n
    )

    return (
        f"===== 以下是 前{n}轮对话内容 (从旧到新，时间戳timestamp格式为 YYYYMMDDHHmmss) =====\n\n"
        f"{'\n\n'.join(['<turn timestamp = '+ str(h.timestamp) + '>\n' + h.turn_text+'\n</turn>' for h in retrieve_turns])}"
        f"\n\n===== 以上是 前{n}轮对话内容 ====="""
    )