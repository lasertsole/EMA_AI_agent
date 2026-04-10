import sys
from pathlib import Path

# 添加项目根目录到 Python 搜索路径
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from context_engine.viking_memory.store import get_db

if __name__ == "__main__":
    db = get_db()