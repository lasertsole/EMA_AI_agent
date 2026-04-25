"""Spawn tool for creating background subagents."""

from typing import Any, Type
from langchain.tools import BaseTool
from subagent import SubagentManager
from pydantic import BaseModel, Field

class SubagentInput(BaseModel):
    task: str = Field(..., description="Subtasks to execute")

class SubagentTool(BaseTool):
    """Tool to spawn a subagent for background task execution."""
    name: str = "subagent"
    description: str = "Spawn a subagent to handle a task in the background. Use for complex or time-consuming tasks that can run independently."
    args_schema: Type[BaseModel] = SubagentInput

    def __init__(self, main_agent_session_id: str):
        self._main_agent_session_id = main_agent_session_id

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = f"{channel}:{chat_id}"

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done. "
            "For deliverables or existing projects, inspect the workspace first "
            "and use a dedicated subdirectory when helpful."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
            },
            "required": ["task"],
        }

    async def execute(self, task: str, label: str | None = None, **kwargs: Any) -> str:
        """Spawn a subagent to execute the given task."""
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_key=self._session_key,
        )


def build_subagent_tool() -> SubagentTool:
    tool: SubagentTool = SubagentTool()
    tool.handle_tool_error = True
    return tool