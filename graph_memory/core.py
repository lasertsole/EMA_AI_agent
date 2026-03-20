import math
import json
from typing import Any, List, TypedDict
from langchain_core.messages import BaseMessage, ToolMessage

class SliceLastTurn(TypedDict):
    messages: List[Any]
    tokens: int
    dropped: int

def estimate_msg_tokens(msg: BaseMessage) -> int:
    content = msg.content

    if isinstance(content, str):
        text = content
    else:
        text = json.dumps(content) if content is not None else ""

        return math.ceil(len(text) / 3)

def slice_last_turn(messages: List[BaseMessage]) -> SliceLastTurn:
    if len(messages)==0:
        return { "messages": [], "tokens": 0, "dropped": 0 }

    last_user_idx = -1

    for i, msg in enumerate(reversed(messages)):
        if msg["role"] == "user":
            last_user_idx = len(messages) - 1 - i
            break

    if last_user_idx < 0:
        last_user_idx = 0

        kept = messages[last_user_idx:]
        dropped = last_user_idx

        TOOL_MAX = 6000
        def truncate_msg(msg: BaseMessage)-> BaseMessage:
            if not isinstance(msg, ToolMessage):
                return msg

            content = msg.get("content", "")
            if not isinstance(content, str):
                text:str = json.dumps(content) if content is not None else ""
            else:
                text:str = content

            if len(text) <= TOOL_MAX:
                return msg

            head_len = int(TOOL_MAX * 0.6)
            tail_len = int(TOOL_MAX * 0.3)

            truncated_text = (
                f"{text[:head_len]}\n"
                f"...[truncated {len(text) - head_len - tail_len} chars]...\n"
                f"{text[-tail_len:]}"
            )

            return msg.model_copy(deep=True, update={"content": truncated_text})

        kept = [truncate_msg(msg) for msg in kept]

        tokens = 0
        for msg in kept:
            tokens += estimate_msg_tokens(msg)

        return { "messages": kept, "tokens": tokens, "dropped": dropped }
