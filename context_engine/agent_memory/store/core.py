import json
import math
import time
import random
import string
import sqlite3
from typing import Any
from ..type import Turn, to_turn
from pub_func import generate_tsid
from models import embed_model, reranker_model

# ─── 工具方法 ─────────────────────────────────────────────────────
def get_timestamp() -> int:
    return int(time.time() * 1000)

def uid(p: str) -> str:
    timestamp = get_timestamp()
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))

    return f"{p}-{timestamp}-{random_str}"

# ─── sqlite CRUD ───────────────────────────────────────────────

def add_turn(db: sqlite3.Connection, session_id: str, turn_text: str):
    with db:  # 自动管理 BEGIN/COMMIT/ROLLBACK
        timestamp: str = generate_tsid()
        id: str = uid("s")

        turn_text_embedding: list[float] = embed_model.embed_query(turn_text)

        db.execute("""
            INSERT INTO turns (id, session_id, turn_text, embedding, timestamp)
            VALUES (?,?,?,?,?)
        """, (id, session_id, turn_text, json.dumps(turn_text_embedding), timestamp))

def delete_turn_by_ids(db: sqlite3.Connection, ids: list[str]):
    """批量删除 turn 记录"""
    if not ids:
        return
    with db:
        placeholders = ','.join(['?'] * len(ids))
        db.execute(f"""
            DELETE FROM turns WHERE id IN ({placeholders})
        """, ids)

def fetch_and_delete_earliest_turns_by_session_id(db: sqlite3.Connection, session_id: str, n: int = 5) -> list[Turn]:
    """查询并删除指定 session_id 的最早 n 条 turn 记录

    Args:
        db: SQLite 数据库连接
        session_id: 会话 ID
        n: 要查询和删除的记录数量，默认 5

    Returns:
        被删除的 Turn 对象列表（按时间顺序排列）
    """
    db.row_factory = sqlite3.Row

    # 第一步：查询最早 n 条数据
    with db:
        rows = db.execute("""
            SELECT * FROM turns 
            WHERE session_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (session_id, n)).fetchall()

        if not rows:
            return []

        # 转换为 Turn 对象
        deleted_turns: list[Turn] = []
        ids_to_delete: list[str] = []

        for row in rows:
            row_dict = dict(row)
            deleted_turns.append(to_turn(row_dict))
            ids_to_delete.append(row_dict['id'])

        # 第二步：删除这些记录
        if ids_to_delete:
            delete_turn_by_ids(db, ids_to_delete)

    return deleted_turns

def get_turns(
        db: sqlite3.Connection,
        session_id: str,
        query: str,
        limit: int = 5,
        min_score: float = 0.5,
)-> list[Turn]:
    db.row_factory = sqlite3.Row

    """以下是用余弦相似度 筛选出符合条件的turns"""
    selected_turns_by_embedding: list[Turn] = []

    with db:
        rows = db.execute(f"""
            SELECT * FROM turns WHERE turns.session_id = ?
        """, (session_id,)).fetchall()

    query_vec: list[float] = embed_model.embed_query(query)
    q_norm: float = math.sqrt(sum(x * x for x in query_vec))

    for row in rows:
        row = dict(row)
        v: list[float] = json.loads(row['embedding'])
        min_len = min(len(v), len(query_vec))

        dot = sum(v[i] * query_vec[i] for i in range(min_len))
        v_norm = math.sqrt(sum(v[i] * v[i] for i in range(min_len)))

        score: float = dot / (v_norm * q_norm + 1e-9)
        if score > min_score:
            selected_turns_by_embedding.append(to_turn(row))

            # 如果已经满足limit的3倍，则停止
            if len(selected_turns_by_embedding) >= limit * 3:
                break
    """以上是用余弦相似度 筛选出符合条件的turns"""

    """以下是用fts5 筛选出符合条件的turns"""
    selected_turns_by_fts5: list[Turn] = []

    # 转义 FTS5 查询字符串
    escaped_query = query.strip()

    # 如果查询为空，跳过 FTS5 搜索
    if not escaped_query:
        pass
    else:
        escaped_query = escaped_query.replace('"', '""')

        # 检查是否包含 FTS5 操作符，如果有则整体加引号
        fts_operators = ['*', '+', '-', '.', '(', ')', '（', '）', '^', '~', '&', '|', ':', 'AND', 'OR', 'NOT']
        needs_quoting = any(op in escaped_query.upper() for op in fts_operators) or any(
            c in escaped_query for c in ["'", '"'])

        if needs_quoting:
            escaped_query = f'"{escaped_query}"'

    with db:
        rows = db.execute(f"""
            SELECT h.*, rank FROM turns_fts fts
            JOIN turns h ON h.rowid = fts.rowid
            WHERE h.session_id = ? AND turns_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (session_id, escaped_query, limit)).fetchall()

        for row in rows:
            row = dict(row)
            selected_turns_by_fts5.append(to_turn(row))
    """以上是用fts5 筛选出符合条件的turns"""

    """以下是用reranker 精选"""
    selected_turns: list[Turn] = [*selected_turns_by_fts5, *selected_turns_by_embedding]
    retrieve_dict: dict[str, Turn] = {r.turn_text: r for r in selected_turns}
    reranker_res: list[dict[str, Any]] = reranker_model.rank(query=query, documents=[r.turn_text for r in selected_turns], top_k=limit)
    res: list[Turn] = [retrieve_dict[r["document"]] for r in reranker_res if r["score"] > 0.0]

    if len(res) > limit:
        res = res[:limit]
    """以上是用reranker 精选"""

    return res

def get_turns_count_by_session_id(db: sqlite3.Connection, session_id: str)-> int:
    """获取指定session_id的turns数量"""
    with db:
        return db.execute(f"""
            SELECT COUNT(*) FROM turns WHERE session_id = ?
        """, (session_id,)).fetchone()[0]

def get_turns_by_lastest_n(db: sqlite3.Connection, session_id: str, last_n: int = 5)-> list[Turn]:
    db.row_factory = sqlite3.Row
    with db:
        rows = db.execute(f"""
            SELECT * FROM turns 
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, last_n)).fetchall()

        res: list[Turn] = []
        for row in rows:
            row = dict(row)
            res.append(to_turn(row))

        res.reverse()
        return res