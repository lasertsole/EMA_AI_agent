import sqlite3
from pathlib import Path
from config import SRC_DIR

_db = None
_db_path = Path(SRC_DIR) / "store/sqlite.db"

def get_db():
    global _db
    if _db:
        return _db

    _db_path.parent.mkdir(parents=True, exist_ok=True)

    _db = sqlite3.connect(_db_path)

    _db.execute("PRAGMA journal_mode = WAL")
    _db.execute("PRAGMA foreign_keys = ON")

    return _db