import numpy as np
from dataclasses import dataclass, field

from pydantic import BaseModel


@dataclass
class GraphNode:
    node_id: int
    text: str
    embedding: np.ndarray = field(repr=False)


@dataclass
class SearchMatch:
    """Represents a search match with combined score."""
    node_id: int
    text: str
    embedding_score: float = 0.0
    fts_score: float = 0.0
    combined_score: float = 0.0
    match_type: str = "hybrid"  # "embedding", "fts", or "hybrid"


@dataclass
class GraphEdge:
    source_id: int
    target_id: int
    bridge_relation: str  # e.g. "developed", "lives_in", "won"

@dataclass
class ExtractRelationResult:
    subject: str
    subject_type: str
    object: str
    object_type: str
    relation: str
    temporal_context: str
    spatial_context: str
    sentiment: str