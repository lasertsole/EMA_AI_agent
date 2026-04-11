import time
import sqlite3
from pathlib import Path
from config import SRC_DIR, CONTEXT_ENGINE_PATH

_db: sqlite3.Connection | None = None
_db_path = Path(SRC_DIR) / "store/viking_memory/viking_memory.db"

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
    steps = [m1_summary, m2_decisions, m3_message, m4_fts5]
    for i in range(cur, len(steps)):
        steps[i](db)
        db.execute("INSERT INTO _migrations (v,at) VALUES (?,?)", (i + 1, int(time.time())))
    db.commit()

# ─── summary 表 ──────────────────────────────────────
def m1_summary(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS summary (
            id              TEXT PRIMARY KEY,
            session_id      TEXT,
            summary         TEXT,
            embedding       BLOB,
            timestamp       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_summary_timestamp ON summary(session_id, timestamp);
    """)

# ─── decisions 表 ──────────────────────────────────────
def m2_decisions(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS decisions (
            summary_id      TEXT REFERENCES summary(id),
            session_id      TEXT,
            decisions       BLOB,
            timestamp       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_decisions_summary_id ON decisions(summary_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(session_id, timestamp);
    
        CREATE TRIGGER IF NOT EXISTS decisions_cascade_delete AFTER DELETE ON summary
        BEGIN
            DELETE FROM decisions WHERE summary_id = OLD.id;
        END;
    """)

# ─── message 表 ──────────────────────────────────────
def m3_message(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS message (
            summary_id      TEXT REFERENCES summary(id),
            session_id      TEXT,
            turn_text        TEXT,
            embedding       BLOB,
            timestamp       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_message_summary_id ON message(summary_id);
        CREATE INDEX IF NOT EXISTS idx_message_timestamp ON message(session_id, timestamp);
    
        CREATE TRIGGER IF NOT EXISTS message_cascade_delete AFTER DELETE ON summary
        BEGIN
            DELETE FROM message WHERE summary_id = OLD.id;
        END;
    """)

# ─── FTS5 全文索引 ───────────────────────────────────────────
def m4_fts5(db: sqlite3.Connection) -> None:
    try:
        db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5(
                turn_text,
                content=gm_nodes,
                content_rowid=rowid,
                tokenize='simple'
            );

            CREATE TRIGGER IF NOT EXISTS message_ai AFTER INSERT ON message
            BEGIN
                INSERT INTO message_fts(rowid, turn_text)
                VALUES (NEW.rowid, NEW.turn_text);
            END;

            CREATE TRIGGER IF NOT EXISTS message_ad AFTER DELETE ON message
            BEGIN
                INSERT INTO message_fts(message_fts, rowid, turn_text)
                VALUES ('delete', OLD.rowid, OLD.turn_text);
            END;

            CREATE TRIGGER IF NOT EXISTS message_au AFTER UPDATE ON message
            BEGIN
                INSERT INTO message_fts(message_fts, rowid, turn_text)
                VALUES ('delete', OLD.rowid, OLD.turn_text);
                INSERT INTO message_fts(rowid, turn_text)
                VALUES (NEW.rowid, NEW.turn_text);
            END;
        """)
    except Exception as e:
        print(f"[WARN] FTS5 not available, falling back to LIKE search: {e}")