"""Session storage for chat history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Any
from config import SESSIONS_DIR
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

def _current_jsonl_path(session_id: str) -> str:
    return (Path(SESSIONS_DIR) / f"{session_id}/current.jsonl").as_posix()

def read_current_from_session(session_id: str) -> list[dict[str, Any]]:
    path: Path = Path(_current_jsonl_path(session_id))

    if not path.exists():
        return []

    # 如果文件存在但内容为空，则返回空列表
    if path.stat().st_size == 0:
        return []

    text_lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line.strip()) for line in text_lines if len(line) > 0]

def _message_to_dict(message: BaseMessage) -> dict:
    """Convert a BaseMessage to a serializable dict."""
    msg_dict = {
        "type": message.__class__.__name__,
        "content": message.content,
        "additional_kwargs": getattr(message, 'additional_kwargs', {}),
    }

    # Add message-specific attributes
    if hasattr(message, 'name') and message.name is not None:
        msg_dict['name'] = message.name

    if hasattr(message, 'id') and message.id is not None:
        msg_dict['id'] = message.id

    if hasattr(message, 'tool_call_id') and message.tool_call_id is not None:
        msg_dict['tool_call_id'] = message.tool_call_id

    if hasattr(message, 'tool_calls') and message.tool_calls:
        msg_dict['tool_calls'] = message.tool_calls

    if hasattr(message, 'invalid_tool_calls') and message.invalid_tool_calls:
        msg_dict['invalid_tool_calls'] = message.invalid_tool_calls

    return msg_dict

"""以下是持久化消息列表"""
def _dict_to_message(msg_dict: dict) -> BaseMessage:
    """Convert a dict back to a BaseMessage."""
    msg_type = msg_dict.get("type")
    content = msg_dict.get("content", "")
    additional_kwargs = msg_dict.get("additional_kwargs", {})

    # Extract message-specific attributes
    name = msg_dict.get("name")
    msg_id = msg_dict.get("id")
    tool_call_id = msg_dict.get("tool_call_id")
    tool_calls = msg_dict.get("tool_calls", [])
    invalid_tool_calls = msg_dict.get("invalid_tool_calls", [])

    # Add back specific attributes to additional_kwargs if they exist
    kwargs = additional_kwargs.copy()
    if name:
        kwargs['name'] = name
    if msg_id:
        kwargs['id'] = msg_id
    if tool_call_id:
        kwargs['tool_call_id'] = tool_call_id
    if tool_calls:
        kwargs['tool_calls'] = tool_calls
    if invalid_tool_calls:
        kwargs['invalid_tool_calls'] = invalid_tool_calls

    # Create the appropriate message type
    if msg_type == "HumanMessage":
        return HumanMessage(content=content, **kwargs)
    elif msg_type == "AIMessage":
        return AIMessage(content=content, **kwargs)
    elif msg_type == "SystemMessage":
        return SystemMessage(content=content, **kwargs)
    elif msg_type == "ToolMessage":
        return ToolMessage(content=content, **kwargs)
    else:
        # Default fallback for unknown message types
        return HumanMessage(content=content, **kwargs)


def serialize_messages_to_jsonl(messages: List[BaseMessage], session_id: str) -> None:
    """Serialize a List[BaseMessage] to current.jsonl file."""
    path = Path(SESSIONS_DIR) / f"{session_id}/current.jsonl"

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert messages to serializable dicts
    serialized_messages = [_message_to_dict(msg) for msg in messages]

    # Write to file in JSONL format (one JSON object per line)
    with path.open("a", encoding="utf-8") as f:
        for msg_dict in serialized_messages:
            f.write(json.dumps(msg_dict, ensure_ascii=False) + "\n")


def deserialize_messages_from_jsonl(session_id: str) -> List[BaseMessage]:
    """Deserialize messages from current.jsonl file back to List[BaseMessage]."""
    path = Path(SESSIONS_DIR) / f"{session_id}/current.jsonl"

    if not path.exists():
        return []

    # If file exists but is empty, return empty list
    if path.stat().st_size == 0:
        return []

    messages = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg_dict = json.loads(line)
                message = _dict_to_message(msg_dict)
                messages.append(message)
            except json.JSONDecodeError:
                continue

    return messages