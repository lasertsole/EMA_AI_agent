import sqlite3
from pathlib import Path
from config import SRC_DIR

_db: sqlite3.Connection | None = None
_db_path = Path(SRC_DIR) / "store/viking_memory.db"

def get_db():
    global _db
    if _db:
        return _db

    _db_path.parent.mkdir(parents=True, exist_ok=True)
    _db = sqlite3.connect(_db_path, check_same_thread=False)

    _db.execute("PRAGMA journal_mode = WAL")
    _db.execute("PRAGMA foreign_keys = ON")

    return _db

# 仅用于测试：关闭并重置单例
def close_db()->None:
    global _db
    if _db:
      _db.close()
      _db = None