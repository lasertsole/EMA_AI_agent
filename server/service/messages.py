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
from ..DAO import maybe_extract_memory, clear_session as clear_session_DAO
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, ToolCall, ToolCallChunk
from context_engine import after_turn, assemble, rectification_and_standardization, add_history, retrieve_history_prompt, retrieve_history_by_last_n_prompt


def _get_config(session_id: str) -> dict[str, Any]:
    try:
        return {"configurable": {"thread_id": int(session_id)}}
    except ValueError:
        raise Exception("session_id must be an integer")

def _get_agent_history_list(agent: CompiledStateGraph, session_id: str)-> List[BaseMessage]:
    return agent.get_state(config=_get_config(session_id)).values.get("messages", [])

"""以下是组装自带上下文的agent逻辑"""
async def _assemble_agent(session_id: str, multi_modal_message: MultiModalMessage) -> CompiledStateGraph:

    # 创建agent
    agent: CompiledStateGraph = built_agent()

    user_text:str = multi_modal_message.text

    # 获取graph-memory系统提示词
    all_messages: List[BaseMessage] = _get_agent_history_list(agent, session_id)
    assemble_result: Dict[str, str] = await assemble(user_text = user_text, messages = all_messages)
    graph_system_prompt_addition:str = assemble_result.get("system_prompt_addition", "")

    # 获取agent-memory系统提示词
    agent_system_prompt_addition:str  = retrieve_history_prompt(user_text = user_text, session_id = session_id)

    # 获取最近几条对话
    recent_messages_addition:str = retrieve_history_by_last_n_prompt(session_id=session_id)

    # 构建系统提示
    messages: List[BaseMessage] = [
        SystemMessage(
            content=
                build_system_prompt()
                + graph_system_prompt_addition
                # + agent_system_prompt_addition
                + recent_messages_addition
        )
    ]

    content_list:List[dict[str, str]] = [{"type": "text", "text": user_text}]
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

    # 若有用户要求记忆的内容 添加 跨线程记忆中
    user_text: str = multi_modal_message.text
    maybe_extract_memory(user_text)

    # 创建已经组装好上下文的agent
    agent: CompiledStateGraph = await _assemble_agent(session_id, multi_modal_message)
    ai_text:str = ""

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
                            ai_text += res
                            yield SSEMessage(res)

                    if _current_tool_id and msg_chunk.content is not None and msg_chunk.content:
                        res: str = f"\n\n**调用工具 {_current_tool_name} 结束。**\n\n"
                        ai_text += res
                        yield SSEMessage(res)
                        _current_tool_id = ""
                    # 以上是输出工具信息

                    # 以下是对话信息
                    if len(msg_chunk.content) > 0:
                        res: str = msg_chunk.content
                        ai_text += res
                        yield SSEMessage(res)
                    # 以上是对话信息

        else:
            result: dict[str, Any] = await agent.ainvoke(input = None, config = _get_config(session_id))
            res: str = result["messages"][-1].content
            ai_text += res
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
        all_messages: List[BaseMessage] = _get_agent_history_list(agent, session_id)
        last_turn_messages: List[BaseMessage] = slice_last_turn(all_messages)["messages"]
        format_last_turn_messages: List[BaseMessage] = sanitize_tool_use_result_pairing(last_turn_messages)

        # 启动上下文引擎的 后处理
        await after_turn(session_id = session_id, last_turn_messages = format_last_turn_messages)

        # 将用户消息持久化
        add_history(session_id = session_id, user_text=user_text, ai_text=ai_text)


"""以上是返回信息逻辑"""

"""以下是会话结束逻辑"""
async def session_end(session_id: str):
    await rectification_and_standardization(session_id = session_id)
"""以上是会话结束逻辑"""

async def clear_session(session_id: str):
    clear_session_DAO(session_id = session_id)