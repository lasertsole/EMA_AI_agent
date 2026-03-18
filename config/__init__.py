from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
ROOT_DIR = ROOT_DIR / ".."

MEMORY_DIR = ROOT_DIR / "memory"
SESSIONS_DIR = ROOT_DIR / "sessions"
SKILLS_DIR = ROOT_DIR / "skills"
WORKSPACE_DIR = ROOT_DIR / "workspace"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"

# Compression and RAG thresholds
COMPRESS_THRESHOLD = 7_000
MEMORY_THRESHOLD = 10_000
COMPRESS_RATIO = 0.7 # 压缩比例，值越大，旧消息数组（要被压缩的部分）就越大。

# Additional directories
MEMORY_INDEX_DIR = MEMORY_DIR / "index"
KNOWLEDGE_INDEX_DIR = KNOWLEDGE_DIR / "index"