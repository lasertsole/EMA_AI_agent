from pathlib import Path

ROOT_DIR = Path(__file__).parent
ROOT_DIR = ROOT_DIR / ".."
ROOT_DIR = ROOT_DIR.resolve()

ENV_PATH = ROOT_DIR / ".env"

INTERPRETER_PATH = ROOT_DIR / ".venv/Scripts/python"

SRC_DIR = ROOT_DIR / "src"
MODEL_WEIGHT_DIR = SRC_DIR / "model_weight"

SESSIONS_DIR = ROOT_DIR / "sessions"
SKILLS_DIR = ROOT_DIR / "skills"
WORKSPACE_DIR = ROOT_DIR / "workspace"
KNOWLEDGE_DIR = WORKSPACE_DIR / "knowledge"
MEMORY_DIR = WORKSPACE_DIR / "memory"
HEARTBEAT_PATH = WORKSPACE_DIR / "HEARTBEAT.md"

# Additional directories
MEMORY_INDEX_DIR = MEMORY_DIR / "index"
KNOWLEDGE_INDEX_DIR = KNOWLEDGE_DIR / "index"