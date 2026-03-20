import re
import json
import time
import random
import string
import sqlite3
from typing import Any, Optional, List, TypedDict
from ..type import GmNode, GmEdge


def uid(p: str) -> str:
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))

    return f"{p}-{timestamp}-{random_str}"

def to_node(r: dict[str, Any])->GmNode:
    return GmNode(
        id = r["id"],
        type = r["type"],
        name = r["name"],
        description = r["description"] if r["description"] is not None else "",
        content = r["content"],
        status = r["status"],
        validated_count = r["validated_count"],
        source_sessions = json.loads(r["source_sessions"] if r["source_sessions"] is not None else "[]"),
        community_id = r["community_id"],
        pagerank = r["pagerank"] if r["pagerank"] is not None else 0,
        created_at = r["created_at"],
        updated_at = r["updated_at"],
    )

def to_edge(r: dict[str, Any])-> GmEdge:
    return GmEdge(
        id = r["id"],
        from_id = r["from_id"],
        to_id = r["to_id"],
        type = r["type"],
        instruction = r["instruction"],
        condition = r["condition"],
        session_id = r["session_id"],
        created_at = r["created_at"],
    )

def normalize_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r'[\s_]+', '-', name)
    name = re.sub(r'[^a-z0-9\u4e00-\u9fff\-]', '', name)
    name = re.sub(r'-{2,}', '-', name)

    return name.strip('-')

def find_by_name(db: sqlite3.Connection, name: str) -> Optional[GmNode]:
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    r = cursor.execute(
    "SELECT * FROM gm_nodes WHERE name = ?",
    (normalize_name(name),)
    ).fetchone()

    return to_node(r) if r else None

def find_by_id(db: sqlite3.Connection, id: str) -> Optional[GmNode]:
    db.row_factory = sqlite3.Row
    r = db.execute("SELECT * FROM gm_nodes WHERE id = ?", (id,)).fetchone()
    return to_node(r) if r else None

def all_active_nodes(db: sqlite3.Connection) -> List[GmNode]:
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM gm_nodes WHERE status='active'").fetchall()
    return [to_node(row) for row in rows]

def all_edges(db: sqlite3.Connection) -> List[GmEdge]:
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM gm_edges").fetchall()
    return [to_edge(row) for row in rows]

class UpsertResult(TypedDict):
    node: Optional[GmNode]
    isNew: bool


def upsert_node(db: sqlite3.Connection, c: dict, session_id: str) -> UpsertResult:
    name = normalize_name(c['name'])
    ex = find_by_name(db, name)
    now = int(time.time() * 1000)

    if ex:
        old_sessions = json.loads(ex.get('source_sessions', '[]'))
        sessions_set = set(old_sessions)
        sessions_set.add(session_id)
        sessions_json = json.dumps(list(sessions_set))

        content = c['content'] if len(c['content']) > len(ex['content']) else ex['content']
        desc = c['description'] if len(c['description']) > len(ex['description']) else ex['description']
        count = ex['validated_count'] + 1

        with db:
            db.execute("""
                UPDATE gm_nodes 
                SET content=?, description=?, validated_count=?, source_sessions=?, updated_at=? 
                WHERE id=?
            """, (content, desc, count, sessions_json, now, ex['id']))

        ex.update({"content": content, "description": desc, "validated_count": count})
        return {"node": ex, "isNew": False}

    new_id = uid("n")
    sessions_json = json.dumps([session_id])

    with db:
        db.execute("""
            INSERT INTO gm_nodes 
            (id, type, name, description, content, status, validated_count, source_sessions, created_at, updated_at)
            VALUES (?,?,?,?,?, 'active', 1, ?, ?, ?)
        """, (new_id, c['type'], name, c['description'], c['content'], sessions_json, now, now))

    return {"node": find_by_name(db, name), "isNew": True}