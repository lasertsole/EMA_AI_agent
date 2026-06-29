from loguru import logger
from langgraph.types import Command
from langgraph.runtime import Runtime
from runtime import state_register_mem
from typing_extensions import override
from typing import Any, Callable, Awaitable
from langgraph.prebuilt.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain.agents.middleware import AgentMiddleware, AgentState


class ToolLoopPrevention(AgentMiddleware):
    """Prevent the same tool from being called more than N times in a single
    conversation turn.  Counter resets at the start of each new turn via
    ``abefore_agent``.

    Threshold (default: 20) — once a tool's call count exceeds this in one
    turn, subsequent calls to that tool are silently skipped and a warning
    ``ToolMessage`` is returned instead.
    """

    def __init__(self, threshold: int = 20, **kwargs):
        super().__init__(**kwargs)

        self._threshold: int = threshold

    @override
    async def abefore_agent(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Reset per-turn counters at the start of each new conversation turn."""
        session_id: str = state.get("session_id", "")
        if session_id.strip() == "":
            err_text: str = "Not pass session_id"
            logger.error(err_text)
            raise RuntimeError(err_text)

        state_register_mem.set_state(session_id, "turn_tool_counts", {})
        return None

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        session_id: str = request.state.get("session_id", "")
        if session_id.strip() == "":
            err_text: str = "Not pass session_id"
            logger.error(err_text)
            raise RuntimeError(err_text)

        turn_tool_counts: dict[str, int] = state_register_mem.get_state(session_id, "turn_tool_counts", {})
        tool_name: str = request.tool_call.get("name", "unknown")
        count: int = turn_tool_counts.get(tool_name, 0) + 1
        turn_tool_counts[tool_name] = count
        state_register_mem.set_state(session_id, "turn_tool_counts", turn_tool_counts)

        if count > self._threshold:
            return ToolMessage(
                content=(
                    f"Tool [{tool_name}] has been called {count} times in this "
                    f"turn, exceeding the limit of {self._threshold}. "
                    "Its execution has been skipped. "
                    "Please reconsider your approach."
                ),
                tool_call_id=request.tool_call["id"],
                name=tool_name,
                status="error",
            )

        return await handler(request)
