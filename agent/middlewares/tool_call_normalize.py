from typing import Any
from langgraph.runtime import Runtime
from langchain_core.messages import RemoveMessage
from pub_func import sanitize_tool_use_result_pairing
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain.agents.middleware import AgentMiddleware, AgentState


class ToolCallNormalize(AgentMiddleware):
    async def abefore_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *sanitize_tool_use_result_pairing(state["messages"])
            ]
        }