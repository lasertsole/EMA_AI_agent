from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()

MEMORY_DIR = ROOT_DIR / "memory"
SESSIONS_DIR = ROOT_DIR / "sessions"
SKILLS_DIR = ROOT_DIR / "skills"
WORKSPACE_DIR = ROOT_DIR / "workspace"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
STORAGE_DIR = ROOT_DIR / "storage"

# Compression and RAG thresholds
COMPRESS_THRESHOLD = 20_000
MEMORY_THRESHOLD = 10_000

# Additional directories
COMPRESSED_SESSIONS_DIR = KNOWLEDGE_DIR / "compressed"
MEMORY_INDEX_DIR = STORAGE_DIR / "memory"
KNOWLEDGE_INDEX_DIR = STORAGE_DIR / "knowledge"