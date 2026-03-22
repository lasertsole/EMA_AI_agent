import re
import json
import time
import random
import string
import sqlite3
from typing import Any, Optional, List, TypedDict
from ..type import GmNode, GmEdge

# ─── 工具 ─────────────────────────────────────────────────────
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

# 标准化 name：全小写，空格转连字符，保留中文
def normalize_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r'[\s_]+', '-', name)
    name = re.sub(r'[^a-z0-9\u4e00-\u9fff\-]', '', name)
    name = re.sub(r'-{2,}', '-', name)

    return name.strip('-')

# ─── 节点 CRUD ───────────────────────────────────────────────
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
    ex: GmNode = find_by_name(db, name)
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


def deprecate(db: sqlite3.Connection, node_id: str) -> None:
    """将指定节点标记为已弃用"""
    db.execute(
        "UPDATE gm_nodes SET status='deprecated', updated_at=? WHERE id=?",
        (int(time.time() * 1000), node_id)
    )


# 合并两个节点：keepId 保留，mergeId 标记 deprecated，边迁移
def merge_nodes(db: sqlite3.Connection, keep_id: str, merge_id: str) -> None:
    """
    合并两个节点：保留 keep_id，将 merge_id 标记为已弃用，并迁移其边关系
    """
    # 获取两个节点的信息
    keep = find_by_id(db, keep_id)
    merge = find_by_id(db, merge_id)
    if not keep or not merge:
        return

    # 合并属性：取内容更长的作为新内容，累加验证次数，合并会话来源
    sessions = list(set(keep.source_sessions + merge.source_sessions))
    count = keep.validated_count + merge.validated_count
    content = keep.content if len(keep.content) >= len(merge.content) else merge.content
    desc = keep.description if len(keep.description) >= len(merge.description) else merge.description

    # 更新保留节点的信息
    db.execute(
        "UPDATE gm_nodes SET content=?, description=?, validated_count=?, "
        "source_sessions=?, updated_at=? WHERE id=?",
        (content, desc, count, json.dumps(sessions), int(time.time() * 1000), keep_id)
    )

    # 迁移边关系：将指向 merge_id 的边重新指向 keep_id
    db.execute("UPDATE gm_edges SET from_id=? WHERE from_id=?", (keep_id, merge_id))
    db.execute("UPDATE gm_edges SET to_id=? WHERE to_id=?", (keep_id, merge_id))

    # 删除自环（防止出现 keep_id → keep_id 的无效边）
    db.execute("DELETE FROM gm_edges WHERE from_id = to_id")

    # 删除重复边（相同 from_id, to_id, type 的只保留一条）
    db.execute("""
        DELETE FROM gm_edges WHERE id NOT IN (
            SELECT MIN(id) FROM gm_edges GROUP BY from_id, to_id, type
        )
    """)

    # 最后将被合并的节点标记为已弃用
    deprecate(db, merge_id)

def update_pageranks(db: sqlite3.Connection, scores: dict) -> None:
    """批量更新 PageRank 分数"""
    cursor = db.cursor()
    try:
        db.execute("BEGIN")
        for node_id, score in scores.items():
            cursor.execute("UPDATE gm_nodes SET pagerank=? WHERE id=?", (score, node_id))
        db.execute("COMMIT")
    except Exception as e:
        db.execute("ROLLBACK")
        raise e


def update_communities(db: sqlite3.Connection, labels: dict) -> None:
    """批量更新社区 ID"""
    cursor = db.cursor()
    try:
        db.execute("BEGIN TRANSACTION")
        # 使用 executemany 进行批量操作
        cursor.executemany(
            "UPDATE gm_nodes SET community_id=? WHERE id=?",
            [(cid, node_id) for node_id, cid in labels.items()]
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

# ─── 边 CRUD ─────────────────────────────────────────────────
def upsert_edge(
        db: sqlite3.Connection,
        edge_data: dict
) -> None:
    """插入或更新边关系：如果已存在则更新，否则创建新记录"""
    # 检查是否已存在相同的边（from_id, to_id, type）
    existing = db.execute(
        "SELECT id FROM gm_edges WHERE from_id=? AND to_id=? AND type=?",
        (edge_data['fromId'], edge_data['toId'], edge_data['type'])
    ).fetchone()

    if existing:
        # 已存在则更新 instruction
        db.execute(
            "UPDATE gm_edges SET instruction=? WHERE id=?",
            (edge_data['instruction'], existing[0])
        )
    else:
        # 不存在则插入新记录
        db.execute(
            """INSERT INTO gm_edges 
            (id, from_id, to_id, type, instruction, condition, session_id, created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                uid("e"),  # 生成唯一ID
                edge_data['fromId'],
                edge_data['toId'],
                edge_data['type'],
                edge_data['instruction'],
                edge_data.get('condition'),  # 使用get避免KeyError
                edge_data['sessionId'],
                int(time.time() * 1000)  # 当前时间戳
            )
        )


def edges_from(db: sqlite3.Connection, node_id: str) -> list:
    """获取从指定节点出发的所有边"""
    rows = db.execute("SELECT * FROM gm_edges WHERE from_id=?", (node_id,)).fetchall()
    return [to_edge(dict(row)) for row in rows]


def edges_to(db: sqlite3.Connection, node_id: str) -> list:
    """获取指向指定节点的所有边"""
    rows = db.execute("SELECT * FROM gm_edges WHERE to_id=?", (node_id,)).fetchall()
    return [to_edge(dict(row)) for row in rows]


# ─── FTS5 搜索 ───────────────────────────────────────────────
_fts5_available: bool | None = None

def fts5_available(db: sqlite3.Connection) -> bool:
    """检查数据库是否支持FTS5全文搜索"""
    global _fts5_available
    if _fts5_available is not None:
        return _fts5_available

    try:
        db.execute("SELECT * FROM gm_nodes_fts LIMIT 0").fetchall()
        _fts5_available = True
    except Exception:
        _fts5_available = False

    return _fts5_available


def search_nodes(db: sqlite3.Connection, query: str, limit: int = 6) -> list:
    """搜索节点：优先使用FTS5全文搜索，降级为LIKE模糊匹配"""
    # 解析查询词
    terms = [term for term in query.strip().split() if term][:8]
    if not terms:
        return top_nodes(db, limit)

    # 优先尝试FTS5搜索
    if fts5_available(db):
        try:
            fts_query = " OR ".join(f'"{term.replace('"', "")}"' for term in terms)
            sql = """
                SELECT n.*, rank FROM gm_nodes_fts fts
                JOIN gm_nodes n ON n.rowid = fts.rowid
                WHERE gm_nodes_fts MATCH ? AND n.status = 'active'
                ORDER BY rank LIMIT ?
            """
            rows = db.execute(sql, (fts_query, limit)).fetchall()
            if rows:
                return [to_node(dict(row)) for row in rows]
        except Exception:
            # FTS查询失败，降级到普通搜索
            pass

    # 降级方案：使用LIKE进行模糊匹配
    where_conditions = " OR ".join(["(name LIKE ? OR description LIKE ? OR content LIKE ?)" for _ in terms])
    like_values = [f"%{term}%" for term in terms for _ in range(3)]  # 每个term对应name/desc/content

    sql = f"""
        SELECT * FROM gm_nodes WHERE status='active' AND ({where_conditions})
        ORDER BY pagerank DESC, validated_count DESC, updated_at DESC LIMIT ?
    """
    rows = db.execute(sql, (*like_values, limit)).fetchall()
    return [to_node(dict(row)) for row in rows]


def top_nodes(db: sqlite3.Connection, limit: int = 6) -> list:
    """获取热门节点：按pagerank、验证次数和更新时间排序"""
    sql = """
        SELECT * FROM gm_nodes WHERE status='active'
        ORDER BY pagerank DESC, validated_count DESC, updated_at DESC LIMIT ?
    """
    rows = db.execute(sql, (limit,)).fetchall()
    return [to_node(dict(row)) for row in rows]
