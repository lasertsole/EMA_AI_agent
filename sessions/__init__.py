"""Sessions package."""
from .store import *
from typing import Any
from .history_index import *
from workspace.prompt_builder import build_system_prompt
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage

def to_messages(history: list[dict[str, Any]], user_input: str) -> list[BaseMessage]:
    """将历史对话和当前用户输入拼接成消息队列"""
    messages: list[BaseMessage] = [SystemMessage(content=build_system_prompt())]
    for m in history:
        role = m.get("role")
        if role == "user":
            messages.append(HumanMessage(content=m.get("content", "")))
        elif role == "assistant":
            messages.append(AIMessage(content=m.get("content", "")))
        elif role == "tool":
            messages.append(
                ToolMessage(
                    content=m.get("content", ""),
                    tool_call_id=m.get("tool_call_id", ""),
                )
            )
    messages.append(HumanMessage(content = user_input))
    return messages