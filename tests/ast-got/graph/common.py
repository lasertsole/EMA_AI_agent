from enum import Enum
from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field

class TimestampedModel(BaseModel):
    created_at: datetime
    updated_at: datetime

    def __init__(selfself, **data):
        now = datetime.now()
        if "created_at" not in data:
            data["created_at"] = now
        if "updated_at" not in data:
            data["updated_at"] = now
        super().__init__(**data)

    def touch(self):
        """Updates the updated_at timestamp."""
        self.updated_at = datetime.now()

class RevisionRecord(BaseModel):
    timestamp: datetime = Field(default_factory = datetime.now)
    user_or_process: str
    action: str
    changes_made: dict[str, Any] = {}
    reason: str = ""

class EpistemicStatus(str, Enum):
    ASSUMPTION = "assumption"
    HYPOTHESIS = "hypothesis"
    EVIDENCE_SUPPORTED = "evidence_supported"
    EVIDENCE_CONTRADICTED = "evidence_contradicted"
    THEORETICALLY_DERIVED = "theoretically_derived"
    WIDELY_ACCEPTED = "widely_accepted"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"
    INFERRED = "inferred"
    SPECULATION = "speculation"

class ConfidenceVector(BaseModel):
    empirical_support: float = Field(
        default=0.5, description="Must be between 0.0 and 1.0"
    )
    theoretical_basis: float = Field(
        default=0.5, description="Must be between 0.0 and 1.0"
    )
    methodological_rigor: float = Field(
        default=0.5, description="Must be between 0.0 and 1.0"
    )
    consensus_alignment: float = Field(
        default=0.5, description="Must be between 0.0 and 1.0"
    )

    def to_list(self) -> list[float]:
        """
        Returns the confidence vector as a list of four float values in a fixed order.
        """
        return [
            self.empirical_support,
            self.theoretical_basis,
            self.methodological_rigor,
            self.consensus_alignment,
        ]

    @classmethod
    def from_list(cls, values: list[float]) -> "ConfidenceVector":
        if len(values) != 4:
            raise ValueError("Confidence list must have exactly 4 values.")
        return cls(
            empirical_support=values[0],
            theoretical_basis=values[1],
            methodological_rigor=values[2],
            consensus_alignment=values[3],
        )

    @property
    def average_confidence(self) -> float:
        return sum(self.to_list()) / 4.0