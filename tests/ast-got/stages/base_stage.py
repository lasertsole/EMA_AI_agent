from typing import Any, Optional
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from ..graph import GoTProcessorSessionData

class StageOutput(BaseModel):
    """Standard output structure for each stage."""

    summary: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    next_stage_context_update: dict[str, Any] = Field(default_factory=dict)
    logs: str = ""

class BaseStage(ABC):
    """Abstract Base Class for all stages in the ASR-GoT pipeline."""
    stage_name: str = "UnknownStage"  # Override in subclasses

    @abstractmethod
    async def execute(
        self,
        current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        """
        Executes the logic for this stage.

        Args:
        current_session_data: Contains all accumulated data for the current session,
        including initial query, parameters, and outputs from previous stages.

        Returns:
        A StageOutput object containing a summary, metrics, and any data to update
        the session context for subsequent stages.
        """
        # This is an abstract method - concrete implementations must return a StageOutput
        raise NotImplementedError("Subclasses must implement execute method")