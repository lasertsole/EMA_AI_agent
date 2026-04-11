import json
import time
import random
import string
import sqlite3
from typing import Optional
from pub_func import generate_tsid
from ..type import Summary, Decisions, Message, to_summary, to_decisions, to_message

# ─── 工具 ─────────────────────────────────────────────────────
def get_timestamp() -> int:
    return int(time.time() * 1000)

def uid(p: str) -> str:
    timestamp = get_timestamp()
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))

    return f"{p}-{timestamp}-{random_str}"

# ─── CRUD ───────────────────────────────────────────────

def add_history(db: sqlite3.Connection, session_id: str, summary: str, summary_embedding: list[float], decisions: list[str], turn_text: str, turn_text_embedding: list[float]):
    with db:  # 自动管理 BEGIN/COMMIT/ROLLBACK
        timestamp: str = generate_tsid()
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
            INSERT INTO message (summary_id, session_id, turn_text, embedding, timestamp)
            VALUES (?,?,?,?,?)
        """, (summary_id, session_id, turn_text, json.dumps(turn_text_embedding), timestamp))

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

def get_summaries(db: sqlite3.Connection, session_id: str, time_start: Optional[str] = None, time_end: Optional[str] = None) -> list[Summary]:
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
        """, (session_id,)).fetchall()

        res: list[Summary] = []
        for row in rows:
            row = dict(row)
            res.append(to_summary(row))

        return res

def get_decisions(db: sqlite3.Connection, summary_ids: list[str])-> list[Decisions]:
    db.row_factory = sqlite3.Row
    with db:
        rows = db.execute(f"""
            SELECT * FROM decisions WHERE summary_id IN ({','.join(['?'] * len(summary_ids))})
        """, summary_ids).fetchall()

        res: list[Decisions] = []
        for row in rows:
            row = dict(row)
            res.append(to_decisions(row))

        return res

def get_messages_by_summary_id(db: sqlite3.Connection, summary_ids: list[str])-> list[Message]:
    db.row_factory = sqlite3.Row
    with db:
        rows = db.execute(f"""
            SELECT * FROM message WHERE summary_id IN ({','.join(['?'] * len(summary_ids))})
        """, summary_ids).fetchall()

        res: list[Message] = []
        for row in rows:
            row = dict(row)
            res.append(to_message(row))

        return res

def get_messages_by_last_n(db: sqlite3.Connection, session_id: str, last_n: int = 5)-> list[Message]:
    db.row_factory = sqlite3.Row
    with db:
        rows = db.execute(f"""
            SELECT * FROM message 
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, last_n)).fetchall()

        res: list[Message] = []
        for row in rows:
            row = dict(row)
            res.append(to_message(row))

        return res

def get_messages_by_match_text(db: sqlite3.Connection, session_id: str, match_text: str, limit: int = 6, time_start: Optional[str] = None, time_end: Optional[str] = None)-> list[Message]:
    db.row_factory = sqlite3.Row

    conditions: list[str] = ["m.session_id = ?"]
    if time_start is not None:
        conditions.append(f"m.timestamp >= {time_start}")
    if time_end is not None:
        conditions.append(f"m.timestamp <= {time_end}")
    where_clause: str = " AND ".join(conditions)

    with db:
        rows = db.execute(f"""
                SELECT m.*, rank FROM message_fts fts
                JOIN message m ON m.rowid = fts.rowid
                WHERE {where_clause} AND message_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (session_id, match_text, limit)).fetchall()

        res: list[Message] = []
        for row in rows:
            row = dict(row)
            res.append(to_message(row))

        return res