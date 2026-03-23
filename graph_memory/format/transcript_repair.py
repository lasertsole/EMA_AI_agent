"""
graph-memory — Transcript Repair

Tool use/result pairing repair for assembled context.

裁剪消息后修复 tool_use/toolResult 配对，防止 OpenClaw 报 "Message ordering conflict"
"""

import time
from typing import TypedDict, List, Set, Dict, Any, Optional


class AgentMessageLike(TypedDict, total=False):
    """Agent 消息类型"""
    role: str
    content: Any
    tool_call_id: Optional[str]
    tool_use_id: Optional[str]
    tool_name: Optional[str]
    stop_reason: Optional[str]
    is_error: Optional[bool]
    timestamp: Optional[int]


class ToolCallLike(TypedDict):
    """工具调用类型"""
    id: str
    name: Optional[str]


TOOL_CALL_TYPES = {
    "toolCall", "toolUse", "tool_use", "tool-use",
    "functionCall", "function_call",
}


def extract_tool_call_id(block: Dict[str, Any]) -> Optional[str]:
    """
    从工具调用块中提取 ID

    Args:
        block: 工具调用字典

    Returns:
        工具调用 ID，如果不存在则返回 None
    """
    if isinstance(block.get('id'), str) and block['id']:
        return block['id']

    if isinstance(block.get('call_id'), str) and block['call_id']:
        return block['call_id']

    return None


def extract_tool_calls_from_assistant(msg: AgentMessageLike) -> List[ToolCallLike]:
    """
    从助手消息中提取工具调用列表

    Args:
        msg: 助手消息

    Returns:
        工具调用列表
    """
    content = msg.get('content')

    if not isinstance(content, list):
        return []

    calls: List[ToolCallLike] = []

    for block in content:
        if not block or not isinstance(block, dict):
            continue

        call_id = extract_tool_call_id(block)

        if not call_id:
            continue

        block_type = block.get('type')

        if isinstance(block_type, str) and block_type in TOOL_CALL_TYPES:
            calls.append({
                'id': call_id,
                'name': block.get('name') if isinstance(block.get('name'), str) else None,
            })

    return calls


def extract_tool_result_id(msg: AgentMessageLike) -> Optional[str]:
    """
    从工具结果消息中提取 ID

    Args:
        msg: 工具结果消息

    Returns:
        工具调用 ID，如果不存在则返回 None
    """
    tool_call_id = msg.get('tool_call_id')
    if isinstance(tool_call_id, str) and tool_call_id:
        return tool_call_id

    tool_use_id = msg.get('tool_use_id')
    if isinstance(tool_use_id, str) and tool_use_id:
        return tool_use_id

    return None


def make_missing_tool_result(tool_call_id: str, tool_name: Optional[str] = None) -> AgentMessageLike:
    """
    创建缺失的工具结果消息

    Args:
        tool_call_id: 工具调用 ID
        tool_name: 工具名称（可选）

    Returns:
        虚拟的工具结果消息
    """
    return {
        'role': 'toolResult',
        'tool_call_id': tool_call_id,
        'tool_name': tool_name or 'unknown',
        'content': [{'type': 'text', 'text': "[graph-memory] tool result missing after context trim." }],
        'is_error': True,
        'timestamp': int(time.time() * 1000),
    }


def sanitize_tool_use_result_pairing(messages: List[AgentMessageLike]) -> List[AgentMessageLike]:
    """
    修复工具调用和结果的配对关系

    裁剪消息后修复 tool_use/toolResult 配对，防止 OpenClaw 报 "Message ordering conflict"

    Args:
        messages: 消息列表

    Returns:
        修复后的消息列表
    """
    out: List[AgentMessageLike] = []
    seen_tool_result_ids: Set[str] = set()
    changed = False

    def push_tool_result(msg: AgentMessageLike) -> None:
        """添加工具结果消息，避免重复"""
        nonlocal changed

        result_id = extract_tool_result_id(msg)

        if result_id and result_id in seen_tool_result_ids:
            changed = True
            return

        if result_id:
            seen_tool_result_ids.add(result_id)

        out.append(msg)

    i = 0
    while i < len(messages):
        msg = messages[i]

        if not msg or not isinstance(msg, dict):
            out.append(msg)
            i += 1
            continue

        role = msg.get('role')

        # 非助手消息处理
        if role != 'assistant':
            if role != 'toolResult':
                out.append(msg)
            else:
                changed = True

            i += 1
            continue

        stop_reason = msg.get('stop_reason')

        # 错误状态直接保留
        if stop_reason in ('error', 'aborted'):
            out.append(msg)
            i += 1
            continue

        # 提取工具调用
        tool_calls = extract_tool_calls_from_assistant(msg)

        if not tool_calls:
            out.append(msg)
            i += 1
            continue

        tool_call_ids = {t['id'] for t in tool_calls}
        span_results_by_id: Dict[str, AgentMessageLike] = {}
        remainder: List[AgentMessageLike] = []

        # 查找后续的工具结果
        j = i + 1

        while j < len(messages):
            next_msg = messages[j]

            if not next_msg or not isinstance(next_msg, dict):
                remainder.append(next_msg)
                j += 1
                continue

            if next_msg.get('role') == 'assistant':
                break

            if next_msg.get('role') == 'toolResult':
                result_id = extract_tool_result_id(next_msg)

                if result_id and result_id in tool_call_ids:
                    if result_id in seen_tool_result_ids:
                        changed = True
                        j += 1
                        continue

                    if result_id not in span_results_by_id:
                        span_results_by_id[result_id] = next_msg

                    j += 1
                    continue

            if next_msg.get('role') != 'toolResult':
                remainder.append(next_msg)
            else:
                changed = True

            j += 1

        # 添加助手消息
        out.append(msg)

        if span_results_by_id and remainder:
            changed = True

        # 添加工具结果（现有的或虚拟的）
        for call in tool_calls:
            existing = span_results_by_id.get(call['id'])

            if existing:
                push_tool_result(existing)
            else:
                changed = True
                push_tool_result(make_missing_tool_result(
                    tool_call_id=call['id'],
                    tool_name=call.get('name'),
                ))

        # 添加剩余消息
        for rem in remainder:
            out.append(rem)

        i = j - 1

    return out if changed else messages
