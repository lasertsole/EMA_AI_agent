import requests
from robyn import SSEMessage
from config import ASSISTANT_NAME
from type import MultiModalMessage
from agent import built_agent, ModelType
from langchain.messages import AIMessageChunk
from typing import AsyncGenerator, Any, Dict, List
from langgraph.graph.state import CompiledStateGraph
from workspace.prompt_builder import build_system_prompt
from pub_func import slice_last_turn, sanitize_tool_use_result_pairing
from sessions import serialize_messages_to_jsonl, deserialize_messages_from_jsonl
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, ToolCall, ToolCallChunk
from context_engine import after_turn, assemble, before_agent_start, rectification_and_standardization
from ..DAO import maybe_archive_history, maybe_extract_memory, read_current_from_session, clear_session as clear_session_DAO


def _get_config(session_id: str) -> dict[str, Any]:
    try:
        return {"configurable": {"thread_id": int(session_id)}}
    except ValueError:
        raise Exception("session_id must be an integer")

"""以下是组装自带上下文的agent逻辑"""
async def _assemble_agent(session_id: str, history: List[dict[str, Any]], multi_modal_message: MultiModalMessage) -> CompiledStateGraph:
    # 将List[dict[str, Any]]转换为List[BaseMessage]
    mes_history: List[BaseMessage] = deserialize_messages_from_jsonl(session_id)

    # 创建agent
    agent: CompiledStateGraph = built_agent()

    user_input:str = multi_modal_message.text

    await before_agent_start(session_id = session_id, human_input_text = user_input)
    assemble_result: Dict[str, str] = await assemble(session_id = session_id, messages = mes_history)
    mes_history = assemble_result.get("messages", [])
    system_prompt_addition = assemble_result.get("system_prompt_addition", "")

    # # 使用viking-memory路由
    # viking_result: Dict[str, Any] = viking_routing(session_id = session_id, user_input = user_input)
    # files: List[str] = viking_result.get("file_names", [])
    # system_prompt_addition:str = viking_result.get("context", "")

    # 加入系统提示
    messages: List[BaseMessage] = [SystemMessage(content=build_system_prompt() + system_prompt_addition)]

    # 消息列表中加入历史对话
    messages += mes_history

    content_list:List[dict[str, str]] = [{"type": "text", "text": multi_modal_message.text}]
    if multi_modal_message.image_base64_list:
        for image_base64 in multi_modal_message.image_base64_list:
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
            # 切换模型
            agent = built_agent(model_type = ModelType.VL_MODEL, enable_tool = False)

    messages.append(HumanMessage(content = content_list))

    # 直接将上下文写入checkpointer内
    agent.update_state(config = _get_config(session_id), values = {"messages": messages})

    return agent

"""以上是组装自带上下文的agent逻辑"""

"""以下是返回信息逻辑"""
_current_tool_name: str = ""
_current_tool_id: str = ""
async def async_generator(session_id: str, multi_modal_message: MultiModalMessage, is_stream: bool = True)-> AsyncGenerator[str, None]:
    global _current_tool_name
    global _current_tool_id

    # 获取历史信息
    history: List[dict[str, Any]] = read_current_from_session(session_id)

    # 若有用户要求记忆的内容 添加 跨线程记忆中
    maybe_extract_memory(multi_modal_message.text)

    # 创建已经组装好上下文的agent
    agent: CompiledStateGraph = await _assemble_agent(session_id, history, multi_modal_message)
    ai_content:str = ""

    try:
        yield SSEMessage(f"{ASSISTANT_NAME}:")
        
        if is_stream:
            # 用已组装好上下文的agent直接输出
            async for chunk in agent.astream(input=None, config=_get_config(session_id), stream_mode="messages"):
                msg_chunk: BaseMessage = chunk[0]
                if isinstance(msg_chunk, AIMessageChunk):
                    # 以下是输出工具信息
                    tool_calls: List[ToolCall] | List[ToolCallChunk] = msg_chunk.tool_calls if msg_chunk.tool_calls and len(
                        msg_chunk.tool_calls) > 0 else msg_chunk.tool_call_chunks
                    if len(tool_calls) > 0 or _current_tool_id.strip():
                        repeat_flag: bool = True  # 防止重复输出工具信息
                        if len(tool_calls) > 0:
                            tool_call = tool_calls[0]

                            if tool_call["name"]:
                                if tool_call["name"].strip() or tool_call["name"].strip() != _current_tool_name:
                                    _current_tool_name = tool_call['name']

                            if tool_call["id"]:
                                if tool_call["id"].strip() or tool_call["id"].strip() != _current_tool_id:
                                    _current_tool_id = tool_call['id']
                                    repeat_flag = False

                        if not repeat_flag:
                            res: str = f"\n\n**调用工具 {_current_tool_name} 中**"
                            ai_content += res
                            yield SSEMessage(res)

                    if _current_tool_id and msg_chunk.content is not None and msg_chunk.content:
                        res: str = f"\n\n**调用工具 {_current_tool_name} 结束。**\n\n"
                        ai_content += res
                        yield SSEMessage(res)
                        _current_tool_id = ""
                    # 以上是输出工具信息

                    # 以下是对话信息
                    if len(msg_chunk.content) > 0:
                        res: str = msg_chunk.content
                        ai_content += res
                        yield SSEMessage(res)
                    # 以上是对话信息

        else:
            result: dict[str, Any] = await agent.ainvoke(input = None, config = _get_config(session_id))
            res: str = result["messages"][-1].content
            ai_content += res
            yield SSEMessage(res)

    except requests.exceptions.HTTPError as e:
        yield SSEMessage(f"请求失败: {e.response.text}")
    except requests.exceptions.Timeout as e:
        yield SSEMessage(f"请求超时: {e.args[0]}")

    except Exception as e:
        raise Exception(e)

    finally:
        # 重置工具信息
        _current_tool_name = ""
        _current_tool_id = ""

        # 获取 格式化后的最后一轮对话的 消息列表
        all_messages: List[BaseMessage] = agent.get_state(config = _get_config(session_id)).values.get("messages", [])
        last_turn_messages: List[BaseMessage] = slice_last_turn(all_messages)["messages"]
        format_last_turn_messages: List[BaseMessage] = sanitize_tool_use_result_pairing(last_turn_messages)

        # 启动上下文引擎的 后处理
        await after_turn(session_id = session_id, last_turn_messages = format_last_turn_messages)

        # 将用户消息持久化
        serialize_messages_to_jsonl(session_id = session_id, messages = format_last_turn_messages)

        # 写出viking时间线
        # enqueue_append_timeline_entry(session_id = session_id, human_content = multi_modal_message.text, ai_content = ai_content)

        # 尝试归档信息
        maybe_archive_history(session_id = session_id, all_messages = all_messages)

"""以上是返回信息逻辑"""

"""以下是会话结束逻辑"""
async def session_end(session_id: str):
    await rectification_and_standardization(session_id = session_id)
"""以上是会话结束逻辑"""

async def clear_session(session_id: str):
    clear_session_DAO(session_id = session_id)