from enum import Enum
from config import ROOT_DIR
from typing import Any, List, Optional, Literal, TypedDict

"""
    graph-memory 类型定义
    节点：TASK / SKILL / EVENT
    边：USED_SKILL / SOLVED_BY / REQUIRES / PATCHES / CONFLICTS_WITH
"""
# ─── 节点 ─────────────────────────────────────────────────────
class NodeType(Enum):
    TASK = "TASK"
    SKILL = "SKILL"
    EVENT = "EVENT"

class NodeStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"

class Node(TypedDict):
    type: NodeType
    name: str
    description: str
    content: str

class GmNode(Node):
    id: str
    status: NodeStatus
    validated_count: int
    source_sessions: List[str]
    community_id: str | None
    pagerank: int
    created_at: int
    updated_at: int

# ─── 边 ───────────────────────────────────────────────────────

class EdgeType(Enum):
    USED_SKILL = "USED_SKILL"
    SOLVED_BY = "SOLVED_BY"
    REQUIRES = "REQUIRES"
    PATCHES = "PATCHES"
    CONFLICTS_WITH = "CONFLICTS_WITH"

class Edge(TypedDict):
    from_id: str
    to_id: str
    type: EdgeType
    instruction: str
    condition: Optional[str]

class GmEdge(Edge):
    id: str
    session_id: str
    created_at: int

# ─── 信号 ─────────────────────────────────────────────────────
class SignalType(Enum):
    TOOL_ERROR = "tool_error"
    TOOL_SUCCESS = "tool_success"
    SKILL_INVOKED = "skill_invoked"
    USER_CORRECTION = "user_correction"
    EXPLICIT_RECORD = "explicit_record"
    TASK_COMPLETED = "task_completed"

class Signal(TypedDict):
    type: SignalType
    turn_index: int
    data: dict[str, Any]

# ─── 提取结果 ─────────────────────────────────────────────────
class ExtractionResult(TypedDict):
    nodes: List[Node]
    edges: List[Edge]

class PromotedSkill(Node):
    type: Literal[NodeType.SKILL]

class FinalizeResult(TypedDict):
    promoted_skills: List[PromotedSkill]
    new_edges: List[Edge]
    invalidations: List[str]

# ─── 召回结果 ─────────────────────────────────────────────────
class RecallResult(TypedDict):
    nodes: List[GmNode]
    edges: List[GmEdge]
    token_estimate: int

# ─── Embedding 配置 ──────────────────────────────────────────
class EmbeddingConfig(TypedDict):
    api_key: Optional[str]
    base_url: Optional[str]
    mode: Optional[str]
    dimensions: Optional[int]

class LLM(TypedDict):
    api_key: Optional[str]
    base_url: Optional[str]
    model: Optional[str]
# ─── 插件配置 ─────────────────────────────────────────────────
class GmConfig(TypedDict):
    db_path: str
    compact_turn_count: int
    recall_max_nodes: int
    recall_max_depth: int
    fresh_tail_count: int
    embedding: Optional[EmbeddingConfig]
    llm:Optional[LLM]
    dedup_threshold: float
    pagerank_damping: float
    pagerank_iterations: int

DEFAULT_CONFIG: GmConfig = GmConfig(
    db_path=f"{ROOT_DIR}/graph-memory/graph-memory.db",
    compact_turn_count = 6,
    recall_max_nodes = 6,
    recall_max_depth = 2,
    fresh_tail_count = 10,
    dedup_threshold = 0.90,
    pagerank_damping = 0.85,
    pagerank_iterations = 20,
    embedding = None,
    llm = None
)