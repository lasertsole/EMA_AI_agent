import json
import time
import random
import string
import sqlite3
from typing import Optional


# ─── 工具 ─────────────────────────────────────────────────────
def get_timestamp() -> int:
    return int(time.time() * 1000)

def uid(p: str) -> str:
    timestamp = get_timestamp()
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))

    return f"{p}-{timestamp}-{random_str}"

# ─── CRUD ───────────────────────────────────────────────

def add_history(db: sqlite3.Connection, session_id: str, summary: str, summary_embedding: list[float], decisions: list[str], ori_text: str, ori_text_embedding: list[float]):
    with db:  # 自动管理 BEGIN/COMMIT/ROLLBACK
        timestamp: int = get_timestamp()
        summary_id: str = uid("s")

        db.execute(
            "INSERT INTO summary (id, session_id, summary, embedding, timestamp) VALUES (?, ?, ?, ?, ?)",
           (summary_id, session_id, summary, json.dumps(summary_embedding), timestamp)
        )

        db.execute("""
            INSERT INTO decisions (summary_id, session_id, decisions, timestamp)
            VALUES (?,?,?,?)
        """, (summary_id, session_id, json.dumps(decisions), timestamp))

        db.execute("""
            INSERT INTO message (summary_id, session_id, ori_text, embedding, timestamp)
            VALUES (?,?,?,?)
        """, (summary_id, session_id, ori_text, json.dumps(ori_text_embedding), timestamp))

def delete_history_by_summary_id(db: sqlite3.Connection, summary_id: str):
    with db:
        db.execute("""
            DELETE FROM summary WHERE id = ?
        """, (summary_id,))

        db.execute("""
            DELETE FROM decisions WHERE summary_id = ?
        """, (summary_id,))

        db.execute("""
            DELETE FROM message WHERE summary_id = ?
        """, (summary_id,))

def delete_history_by_session_id(db: sqlite3.Connection, session_id: str):
    """ 删除历史记录
    (decisions表 和 message表有连带删除触发器， 所以只需要操作summary表)
    """
    with db:
        db.execute("""
            DELETE FROM summary WHERE session_id = ?
        """, (session_id,))

def get_summaries(db: sqlite3.Connection, session_id: str, time_start: Optional[int] = None, time_end: Optional[int] = None) -> list[dict]:
    db.row_factory = sqlite3.Row

    conditions: list[str] = ["summary.session_id = ?"]
    if time_start is not None:
        conditions.append(f"summary.timestamp >= {time_start}")
    if time_end is not None:
        conditions.append(f"summary.timestamp <= {time_end}")
    where_clause: str = " AND ".join(conditions)

    with db:
        rows = db.execute(f"""
            SELECT * FROM summary WHERE {where_clause}
            ORDER BY summary.timestamp DESC
            WHERE {where_clause}
        """, (session_id,)).fetchall()

        return [
            {
                'id': row.id,
                'session_id': row.session_id,
                'summary': row.summary,
                'embedding': json.loads(row.summary_embedding),
                'timestamp': row.timestamp,
            } for row in rows
        ]

def get_decisions(db: sqlite3.Connection, summary_ids: list[str]):
    db.row_factory = sqlite3.Row
    with db:
        rows = db.execute(f"""
            SELECT * FROM decisions WHERE summary_id IN ({','.join(['?'] * len(summary_ids))})
        """, summary_ids).fetchall()
        return [
            {
                'summary_id': row.summary_id,
                'session_id': row.session_id,
                'decisions': json.loads(row.decisions),
                'timestamp': row.timestamp,
            } for row in rows
        ]

def get_messages_by_summary_id(db: sqlite3.Connection, summary_ids: list[str]):
    db.row_factory = sqlite3.Row
    with db:
        rows = db.execute(f"""
            SELECT * FROM message WHERE summary_id IN ({','.join(['?'] * len(summary_ids))})
        """, summary_ids).fetchall()
        return [
            {
                'summary_id': row.summary_id,
                'session_id': row.session_id,
                'ori_text': row.ori_text,
            } for row in rows
        ]

def get_messages_by_match_text(db: sqlite3.Connection, match_text: str, limit: int = 6):
    db.row_factory = sqlite3.Row
    with db:
        rows = db.execute("""
                SELECT m.*, rank FROM message_fts fts
                JOIN message m ON n.rowid = fts.rowid
                WHERE message_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (match_text, limit)).fetchall()
        return [
            {
                'summary_id': row.summary_id,
                'session_id': row.session_id,
                'ori_text': row.ori_text,
                'rank': row.rank
            } for row in rows
        ]