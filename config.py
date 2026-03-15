from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()

MEMORY_DIR = ROOT_DIR / "memory"
SESSIONS_DIR = ROOT_DIR / "sessions"
SKILLS_DIR = ROOT_DIR / "skills"
WORKSPACE_DIR = ROOT_DIR / "workspace"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"

# Compression and RAG thresholds
COMPRESS_THRESHOLD = 10_0
MEMORY_THRESHOLD = 10_0

# Additional directories
MEMORY_INDEX_DIR = MEMORY_DIR / "index"
KNOWLEDGE_INDEX_DIR = KNOWLEDGE_DIR / "index"