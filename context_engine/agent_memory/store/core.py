import json
import math
import time
import random
import string
import sqlite3
from typing import Any
from pub_func import generate_tsid
from ..type import History, to_history
from models import embed_model, reranker_model

# ─── 工具 ─────────────────────────────────────────────────────
def get_timestamp() -> int:
    return int(time.time() * 1000)

def uid(p: str) -> str:
    timestamp = get_timestamp()
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))

    return f"{p}-{timestamp}-{random_str}"

# ─── CRUD ───────────────────────────────────────────────

def add_history(db: sqlite3.Connection, session_id: str, turn_text: str):
    with db:  # 自动管理 BEGIN/COMMIT/ROLLBACK
        timestamp: str = generate_tsid()
        id: str = uid("s")

        turn_text_embedding: list[float] = embed_model.embed_query(turn_text)

        db.execute("""
            INSERT INTO histories (id, session_id, turn_text, embedding, timestamp)
            VALUES (?,?,?,?,?)
        """, (id, session_id, turn_text, json.dumps(turn_text_embedding), timestamp))

def delete_history_by_id(db: sqlite3.Connection, id: str):
    with db:
        db.execute("""
            DELETE FROM histories WHERE id = ?
        """, (id,))

def delete_histories_by_session_id(db: sqlite3.Connection, session_id: str):
    """ 删除历史消息
    """
    with db:
        db.execute("""
            DELETE FROM histories WHERE session_id = ?
        """, (session_id,))

def delete_histories_by_n_days_ago(db: sqlite3.Connection, n_days_ago: int = 7):
    """ 删除历史消息
    """
    bias_tsid:str = generate_tsid(days_offset=-n_days_ago)

    with db:
        db.execute("""
            DELETE FROM histories WHERE timestamp < ?
        """, (bias_tsid,))

def get_histories_by_last_n(db: sqlite3.Connection, session_id: str, last_n: int = 7)-> list[History]:
    db.row_factory = sqlite3.Row
    with db:
        rows = db.execute(f"""
            SELECT * FROM histories 
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, last_n)).fetchall()

        res: list[History] = []
        for row in rows:
            row = dict(row)
            res.append(to_history(row))

        return res

def get_histories(
        db: sqlite3.Connection,
        session_id: str,
        query: str,
        limit: int = 10,
        min_score: float = 0.5,
)-> list[History]:
    db.row_factory = sqlite3.Row

    """以下是用余弦相似度 筛选出符合条件的histories"""
    selected_histories_by_embedding: list[History] = []

    with db:
        rows = db.execute(f"""
            SELECT * FROM histories WHERE histories.session_id = ?
        """, (session_id,)).fetchall()

    query_vec: list[float] = embed_model.embed_query(query)
    q_norm = math.sqrt(sum(x * x for x in query_vec))

    for row in rows:
        row = dict(row)
        v: list[float] = json.loads(row['embedding'])
        min_len = min(len(v), len(query_vec))

        dot = sum(v[i] * query_vec[i] for i in range(min_len))
        v_norm = math.sqrt(sum(v[i] * v[i] for i in range(min_len)))

        score = dot / (v_norm * q_norm + 1e-9)
        if score > min_score:
            selected_histories_by_embedding.append(to_history(row))

            # 如果已经满足limit的3倍，则停止
            if len(selected_histories_by_embedding) >= limit * 3:
                break
    """以上是用余弦相似度 筛选出符合条件的histories"""

    """以下是用fts5 筛选出符合条件的histories"""
    selected_histories_by_fts5: list[History] = []

    # 转义 FTS5 查询字符串
    escaped_query = query.strip()
    if any(c in escaped_query for c in ['"', "'", '*', '+', '-', '.', '(', ')', '^', '~', '&', '|', ':']):
        escaped_query = escaped_query.replace('"', '""')
        escaped_query = f'"{escaped_query}"'

    with db:
        rows = db.execute(f"""
            SELECT h.*, rank FROM histories_fts fts
            JOIN histories h ON h.rowid = fts.rowid
            WHERE h.session_id = ? AND histories_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (session_id, escaped_query, limit)).fetchall()

        for row in rows:
            row = dict(row)
            selected_histories_by_fts5.append(to_history(row))
    """以上是用fts5 筛选出符合条件的histories"""

    """以下是用reranker 精选"""
    selected_histories: list[History] = [*selected_histories_by_fts5, *selected_histories_by_embedding]
    retrieve_dict: dict[str, History] = {r.turn_text: r for r in selected_histories}
    reranker_res: list[dict[str, Any]] = reranker_model.rank(query=query, documents=[r.turn_text for r in selected_histories], top_k=limit)
    res: list[History] = [retrieve_dict[r["document"]] for r in reranker_res if r["score"] > 0.0]

    if len(res) > limit:
        res = res[:limit]
    """以上是用reranker 精选"""

    return res