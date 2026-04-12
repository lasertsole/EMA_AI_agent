import sqlite3
from .type import History
from pub_func import generate_tsid
from models import simple_chat_model
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .store import get_db, add_history as db_add_history, get_histories, get_histories_by_last_n, delete_histories_by_n_days_ago

_db: sqlite3.Connection = get_db()

def add_history(session_id: str, user_text: str, ai_text: str)-> None:
    turn_text: str = f"**user**:{user_text}\n**assistant**:{ai_text}"

    db_add_history(
        db= _db,
        session_id= session_id,
        turn_text= turn_text
    )

class TimeLimited(BaseModel):
    time_start: str | None = Field(default=None, description="起始时间，格式：YYYYMMDDHHmmss", examples= ["20260411154119"])
    time_end: str | None = Field(default=None, description="结束时间，格式：YYYYMMDDHHmmss", examples= ["20260411154119"])

def retrieve_history_prompt(session_id: str, user_text: str) -> str:
    retrieve_histories: list[History] = get_histories(
        db=_db,
        session_id=session_id,
        query=user_text,
        limit=10,
    )

    return (
        "===== 以下是 agent-memory 根据用户输入的内容 匹配到的 历史对话记录 =====\n\n"
        f"{"\n".join([h.turn_text for h in retrieve_histories])}"
        "\n\n===== 以下是 agent-memory 根据用户输入的内容 匹配到的 历史对话记录 ====="""
    )

def retrieve_history_by_last_n_prompt(session_id: str, n: int = 7) -> str:
    retrieve_histories: list[History] = get_histories_by_last_n(
        db=_db,
        session_id=session_id,
        last_n=n
    )

    return (
        f"===== 以下是 前{n}轮对话内容 =====\n\n"
        f"{"\n".join([h.turn_text for h in retrieve_histories])}"
        f"\n\n===== 以上是 前{n}轮对话内容 ====="""
    )

def delete_old_history_by_n_days_ago(n_days_ago: int = 7)-> None:
    if n_days_ago < 0:
        raise ValueError("n_days_ago must be greater than 0")

    delete_histories_by_n_days_ago(db=_db, n_days_ago=n_days_ago)