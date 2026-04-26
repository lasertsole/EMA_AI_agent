"""Spawn tool for creating background subagents."""

import asyncio
from typing import Any, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from subagent import SubagentManager, subagent_manager

class SubagentInput(BaseModel):
    task: str = Field(..., description="Subtasks to execute")

class SubagentTool(BaseTool):
    """Tool to spawn a subagent for background task execution."""
    name: str = "subagent"
    description: str = "Spawn a subagent to handle a task in the background. Use for complex or time-consuming tasks that can run independently."
    args_schema: Type[BaseModel] = SubagentInput

    def __init__(self):
        self._manager: SubagentManager = subagent_manager

    async def _arun(self, task: str, label: str | None = None, **kwargs: Any):
        """Spawn a subagent to execute the given task."""
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_id=self._session_id,
        )

    def _run(self, task: str, label: str | None = None, **kwargs: Any) -> str:
        """Spawn a subagent to execute the given task."""
        return asyncio.run(self._manager.spawn(
            task=task,
            label=label,
            session_id=self._session_id,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
        ))

def build_subagent_tool() -> SubagentTool:
    tool: SubagentTool = SubagentTool()
    tool.handle_tool_error = True
    return tool