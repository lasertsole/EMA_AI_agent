from typing import Any
from pydantic import BaseModel, Field

class GoTProcessorSessionData(BaseModel):
    """Data model for session data maintained by GoTProcessor."""

    session_id: str = Field(default="")
    query: str = ""
    final_answer: str = ""
    final_confidence_vector: str = "0.5,0.5,0.5,0.5"  # Simplified as string
    accumulated_context: dict[str, Any] = Field(default_factory=dict)
    stage_outputs_trace: list[dict[str, Any]] = Field(default_factory=list)