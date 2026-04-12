import time
import sqlite3
from pathlib import Path
from config import SRC_DIR, CONTEXT_ENGINE_PATH

_db: sqlite3.Connection | None = None
_db_path = Path(SRC_DIR) / "store/agent_memory/agent_memory.db"

def get_db():
    global _db
    if _db:
        return _db

    _db_path.parent.mkdir(parents=True, exist_ok=True)
    _db = sqlite3.connect(_db_path, check_same_thread=False)

    _db.enable_load_extension(True)
    _db.load_extension((CONTEXT_ENGINE_PATH / "tokenizer/simple.dll").as_posix())

    _db.execute("PRAGMA journal_mode = WAL")
    _db.execute("PRAGMA foreign_keys = ON")
    migrate(_db)

    return _db

# 仅用于测试：关闭并重置单例
def close_db()->None:
    global _db
    if _db:
      _db.close()
      _db = None

def migrate(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS _migrations (v INTEGER PRIMARY KEY, at INTEGER NOT NULL)")
    cur = db.execute("SELECT MAX(v) as v FROM _migrations").fetchone()[0]
    if cur is None:
        cur = 0
    steps = [build_turns_db, build_turns_fts5_db]
    for i in range(cur, len(steps)):
        steps[i](db)
        db.execute("INSERT INTO _migrations (v,at) VALUES (?,?)", (i + 1, int(time.time())))
    db.commit()

# ─── turns 表 ──────────────────────────────────────
def build_turns_db(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS turns (
            id              TEXT PRIMARY KEY,
            session_id      TEXT,
            turn_text       TEXT,
            embedding       BLOB,
            timestamp       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id);
        CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(timestamp);
    """)

# ─── turns FTS5 全文索引 ───────────────────────────────────────────
def build_turns_fts5_db(db: sqlite3.Connection) -> None:
    try:
        db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
                turn_text,
                content=gm_nodes,
                content_rowid=rowid,
                tokenize='simple'
            );

            CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON turns
            BEGIN
                INSERT INTO turns_fts(rowid, turn_text)
                VALUES (NEW.rowid, NEW.turn_text);
            END;

            CREATE TRIGGER IF NOT EXISTS turns_ad AFTER DELETE ON turns
            BEGIN
                INSERT INTO turns_fts(turns_fts, rowid, turn_text)
                VALUES ('delete', OLD.rowid, OLD.turn_text);
            END;

            CREATE TRIGGER IF NOT EXISTS turns_au AFTER UPDATE ON turns
            BEGIN
                INSERT INTO turns_fts(turns_fts, rowid, turn_text)
                VALUES ('delete', OLD.rowid, OLD.turn_text);
                INSERT INTO turns_fts(rowid, turn_text)
                VALUES (NEW.rowid, NEW.turn_text);
            END;
        """)
    except Exception as e:
        print(f"[WARN] FTS5 not available, falling back to LIKE search: {e}")