from pathlib import Path

ROOT_DIR = Path(__file__).parent
ROOT_DIR = ROOT_DIR / ".."
ROOT_DIR = ROOT_DIR.resolve()

ENV_PATH = ROOT_DIR / ".env"

MEMORY_DIR = ROOT_DIR / "memory"
SESSIONS_DIR = ROOT_DIR / "sessions"
SKILLS_DIR = ROOT_DIR / "skills"
WORKSPACE_DIR = ROOT_DIR / "workspace"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
SRC_DIR = ROOT_DIR / "src"

# Additional directories
MEMORY_INDEX_DIR = MEMORY_DIR / "index"
KNOWLEDGE_INDEX_DIR = KNOWLEDGE_DIR / "index"