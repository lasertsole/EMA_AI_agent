import math
import sqlite3
from typing import Optional, Any
from pub_func import generate_tsid
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from models import simple_chat_model, embed_model, reranker_model
from .store import (get_db, add_history as db_add_history, get_summaries, get_decisions, get_messages_by_match_text,
                    get_messages_by_last_n, delete_history_by_n_days_ago)

_db: sqlite3.Connection = get_db()

class Record(BaseModel):
    l0: str = Field(default="", description="一句话极简概括，10-20字，只说做了什么事，不要带任何前缀符号")
    l1: list[str] = Field(default=[], description="如果本轮有关键步骤内容，列出具体细节.如果没有步骤信息，则不输出", examples= [[
        "- 具体步骤：第一步寻找彩叶本人或手镯，第二步获取手镯，第三步激活手镯连接月读世界",
        "- 搜索策略：先询问相关人员，搜索实验室位置，寻找活动痕迹，重点搜索东京科技园区、大学机械工程系、义体技术研究中心",
        "- 时间线分析：发现辉夜等待八千年与彩叶是现代人的矛盾，推测月读世界时间流速不同或手镯有时空功能",
        "- 备用方案：寻找月读世界其他入口，联系其他知道月读世界的人",
    ]])

def add_history(session_id: str, user_text: str, ai_text: str)-> None:
    if user_text == "" or ai_text == "":
        raise ValueError("user_text or ai_text is empty")

    system = (
        "你是一个技术记录助手。根据完整对话内容，生成两部分输出。使用中文。\n\n"
        "严格按以下格式输出，不要输出任何其他内容：\n"
        "L0 是时间线目录，要极度精简，像书的章节标题。注意：只输出摘要文本本身，不要输出时间戳、不要输出\"- \"前缀，这些由系统自动添加。\n\n"
        "L1 是详细摘要，要包含具体的：\n"
        " - 用了什么步骤、什么方法(如果有的话)\n"
        " - 具体材料、参数等(如果有的话)\n"
        " - 做了什么 遵循什么逻辑 为什么这么做 等(如果有的话)\n"
        " - 事件归因和解决方法(如果有的话)\n"
        " - 确认的结论和共识(如果有的话)\n\n"
        "L1 每条要有足够的细节(如果有的话)，让人不看原文也能知道具体怎么做的,一行一条。"
    )
    user = """===== 对话内容 =====
    {turn_text}

    请按格式生成 [L0] 和 [L1]。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", user)
    ])

    turn_text: str = f"**user**:{user_text}\n**assistant**:{ai_text}"

    record_res: Record = (prompt | simple_chat_model.with_structured_output(Record)).invoke(
        {"turn_text": turn_text},
        max_tokens=800
    )

    summary: str = record_res.l0

    embedding: list[list[float]] = embed_model.embed_documents([summary, turn_text])

    db_add_history(
        db= _db,
        session_id= session_id,
        summary= record_res.l0,
        summary_embedding= embedding[0],
        decisions= record_res.l1,
        turn_text= turn_text,
        turn_text_embedding= embedding[1]
    )

class RetrieveRecord(BaseModel):
    text: str
    timestamp: int

class TimeLimited(BaseModel):
    time_start: str | None = Field(default=None, description="起始时间，格式：YYYYMMDDHHmmss", examples= ["20260411154119"])
    time_end: str | None = Field(default=None, description="结束时间，格式：YYYYMMDDHHmmss", examples= ["20260411154119"])

def _retrieve_by_embedding(session_id: str, query_vec: list[float], min_score: float = 0.6, time_start: Optional[str] = None, time_end: Optional[str] = None) -> list[RetrieveRecord]:
    summaries = get_summaries(db=_db, session_id=session_id, time_start = time_start, time_end = time_end)

    q_norm = math.sqrt(sum(x * x for x in query_vec))
    if q_norm == 0:
        return []

    # 用余弦相似度 筛选出符合条件的summary
    selected_summary_ids: list[str] = []
    for summary in summaries:
        v: list[float] = summary.embedding
        min_len = min(len(v), len(query_vec))

        dot = sum(v[i] * query_vec[i] for i in range(min_len))
        v_norm = math.sqrt(sum(v[i] * v[i] for i in range(min_len)))

        score = dot / (v_norm * q_norm + 1e-9)
        if score > min_score:
            selected_summary_ids.append(summary.id)

    # 根据筛选的summary_id，获取decisions
    decisions = get_decisions(_db, selected_summary_ids)

    return [RetrieveRecord(text="\n".join(d.decisions), timestamp=d.timestamp) for d in decisions]

def _retrieve_by_fts5(session_id: str, user_text: str, limited_count: int = 6, time_start: Optional[str] = None, time_end: Optional[str] = None) -> list[RetrieveRecord]:
    messages = get_messages_by_match_text(db=_db, session_id=session_id, match_text=user_text, time_start=time_start, time_end=time_end)
    messages = messages[:limited_count]

    return [RetrieveRecord(text=m.turn_text, timestamp=m.timestamp) for m in messages]

def retrieve_history(session_id: str, user_text: str) -> list[RetrieveRecord]:
    system = (
        "根据用户输入的内容，提取所需要匹配的时间段 或 对话轮数，时间格式为 YYYYMMDDHHmmss\n"
        f"当前时间为 {generate_tsid()}"
        "example:"
        "- '帮我看看昨天的新闻是什么'-> 当前时间为 20260411154119 time_start: 20260410000000 end_time: 20260411000000" 
        "- '帮我看看7月1号到7月7号之间的新闻是什么'-> time_start: 20270701000000 time_end: 20270708000000"
        "- '帮我看看5分钟前我说了什么'-> 当前时间为 20260411154119 time_start: 20260411153619, 不输出 time_end"
        "如果 用户 说了 ‘刚刚’， ‘刚才’时，不需要输出 time_start 和 time_end"
        "都不匹配时什么都不输出"
    )
    user = """===== 用户输入的内容 =====
        {user_text}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", user)
    ])

    time_limited_res: TimeLimited = (prompt | simple_chat_model.with_structured_output(TimeLimited)).invoke(
        {"user_text": user_text},
        max_tokens=80
    )

    res: list[RetrieveRecord] = []
    last_n: int = 5
    time_start: str = time_limited_res.time_start
    time_end: str = time_limited_res.time_end

    if time_start is None and time_end is None:
        retrieve_mes_by_last_n = get_messages_by_last_n(db=_db, session_id=session_id, last_n=last_n)
        res = [RetrieveRecord(text=r.turn_text, timestamp=r.timestamp) for r in retrieve_mes_by_last_n]


    query_vec: list[float] = embed_model.embed_query(user_text)
    retrieve_by_fts5 = _retrieve_by_fts5(session_id = session_id, user_text = user_text, time_start = time_start, time_end = time_end)
    retrieve_by_embedding = _retrieve_by_embedding(session_id = session_id, query_vec = query_vec, time_start=time_start, time_end=time_end)

    retrieve_list: list[RetrieveRecord] = [*retrieve_by_fts5, *retrieve_by_embedding]
    retrieve_dict: dict[str, RetrieveRecord] = {r.text: r for r in retrieve_list}

    reranker_texts: list[dict[str, Any]] = reranker_model.rank(query=user_text, documents=[r.text for r in retrieve_list], top_k=5)
    reranker_records: list[RetrieveRecord] = [retrieve_dict[r["document"]] for r in reranker_texts]
    res += reranker_records
    print(res)

    return res

def delete_old_history_by_n_days_ago(n_days_ago: int = 7)-> None:
    if n_days_ago < 0:
        raise ValueError("n_days_ago must be greater than 0")
    bias_tsid = generate_tsid(days_offset = -n_days_ago)

    delete_history_by_n_days_ago(db=_db, n_days_ago=bias_tsid)