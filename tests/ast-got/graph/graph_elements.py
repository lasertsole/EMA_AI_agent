import uuid
from enum import Enum
from pydantic import Field
from datetime import datetime
from pydantic import BaseModel
from typing import Any, Optional
from .common import ConfidenceVector, TimestampedModel, EpistemicStatus

class RevisionRecord(BaseModel):
    timestamp: datetime = Field(default_factory = datetime.now)
    user_or_process: str
    action: str
    changes_made: dict[str, Any] = {}
    reason: str = ""

class NodeMetadata(TimestampedModel):
    description: str = ""
    query_context: str = ""
    source_description: str = ""
    epistemic_status: EpistemicStatus = EpistemicStatus.UNKNOWN
    disciplinary_tags: str = ""
    layer_id: str = ""
    impact_score: float = 0.1
    is_knowledge_gap: bool = False
    id: str = Field(default_factory = lambda: str(uuid.uuid4()))
    doi: str = ""
    authors: str = ""
    publication_date: str = ""
    revision_history: list[RevisionRecord] = Field(default_factory=list)

class NodeType(str, Enum):
    ROOT = "root"
    TASK_UNDERSTANDING = "task_understanding"
    DECOMPOSITION_DIMENSION = "decomposition_dimension"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    PLACEHOLDER_GAP = "placeholder_gap"
    INTERDISCIPLINARY_BRIDGE = "interdisciplinary_bridge"
    RESEARCH_QUESTION = "research_question"

class Node(TimestampedModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    type: NodeType = NodeType.HYPOTHESIS
    confidence: ConfidenceVector = Field(default_factory=ConfidenceVector)
    metadata: NodeMetadata = Field(default_factory=NodeMetadata)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Node) and self.id == other.id

    def update_confidence(
        self,
        new_confidence: ConfidenceVector,
        updated_by: str,
        reason: Optional[str] = None,
    ) -> None:
        old_conf = self.confidence.model_dump()
        self.confidence = new_confidence
        self.metadata.revision_history.append(
            RevisionRecord(
                user_or_process = updated_by,
                action = "update_confidence",
                changes_made = {
                    "confidence": {"old": old_conf, "new": new_confidence.model_dump()}
                },
                reason = reason,
            )
        )
        self.touch()