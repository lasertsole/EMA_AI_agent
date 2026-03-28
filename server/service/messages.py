import requests
from robyn import SSEMessage
from pub_func import get_config
from config import ASSISTANT_NAME
from type import MultiModalMessage
from agent import built_agent, ModelType
from langchain.messages import AIMessageChunk
from sessions import viking_routing, load_summary
from typing import AsyncGenerator, Any, Dict, List
from workspace.prompt_builder import build_system_prompt
from ..DAO import enqueue_append_timeline_entry, compress_history, storage_add_chat
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage, ToolCall, ToolCallChunk

# 创建agent
agent = built_agent()

"""以下是组织信息列表逻辑"""
def to_messages(session_id: str, history: List[dict[str, Any]], multi_modal_message: MultiModalMessage) -> List[BaseMessage]:
    global agent

    user_input:str = multi_modal_message.text

    # 使用open-viking路由
    viking_result: Dict[str, Any] = viking_routing(session_id = session_id, user_input = user_input)
    files: List[str] = viking_result.get("file_names", [])
    context:str = viking_result.get("context", "")

    #"""将历史对话和当前用户输入拼接成消息队列"""
    # 加入系统提示
    messages: List[Any] = [SystemMessage(content = build_system_prompt(selected_file_names = files) + context)]

    # 加入摘要
    summary:str = load_summary(session_id=session_id)
    if summary and len(summary) > 0:
        messages.append(HumanMessage(content=summary))

    for m in history:
        role:str = m.get("role")
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

    content_list:List[dict[str, str]] = [{"type": "text", "text": multi_modal_message.text}]
    if multi_modal_message.image_base64_list:
        for image_base64 in multi_modal_message.image_base64_list:
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
            # 切换模型
            agent = built_agent(model_type = ModelType.VL_MODEL, enable_tool = False)

    messages.append(HumanMessage(content = content_list))
    return messages

"""以下是组织信息列表逻辑"""

"""以下是返回信息逻辑"""
current_tool_name: str = ""
current_tool_id: str = ""
async def async_generator(session_id: str, history: List[dict[str, Any]], multi_modal_message: MultiModalMessage)-> AsyncGenerator[str, None]:
    global current_tool_name
    global current_tool_id

    # 创建消息队列
    messages: List[BaseMessage] = to_messages(session_id, history, multi_modal_message)
    messages_dict: Dict[str, List[BaseMessage]] = {"messages": messages}

    ai_content:str = ""

    try:
        yield SSEMessage(f"{ASSISTANT_NAME}:")
        async for chunk in agent.astream(messages_dict, config=get_config(session_id), stream_mode="messages"):
            msg_chunk: BaseMessage = chunk[0]
            if isinstance(msg_chunk, AIMessageChunk):
                # 以下是输出工具信息
                tool_calls: List[ToolCall] | List[ToolCallChunk] = msg_chunk.tool_calls if msg_chunk.tool_calls and len(
                    msg_chunk.tool_calls) > 0 else msg_chunk.tool_call_chunks
                if len(tool_calls) > 0 or current_tool_id.strip():
                    repeat_flag: bool = True  # 防止重复输出工具信息
                    if len(tool_calls) > 0:
                        tool_call = tool_calls[0]

                        if tool_call["name"]:
                            if tool_call["name"].strip() or tool_call["name"].strip() != current_tool_name:
                                current_tool_name = tool_call['name']

                        if tool_call["id"]:
                            if tool_call["id"].strip() or tool_call["id"].strip() != current_tool_id:
                                current_tool_id = tool_call['id']
                                repeat_flag = False

                    if not repeat_flag:
                        res: str = f"\n\n**调用工具 {current_tool_name} 中**"
                        ai_content += res
                        yield SSEMessage(res)

                if current_tool_id and msg_chunk.content is not None and msg_chunk.content:
                    res: str = f"\n\n**调用工具 {current_tool_name} 结束。**\n\n"
                    ai_content += res
                    yield SSEMessage(res)
                    current_tool_id = ""
                # 以上是输出工具信息

                # 以下是对话信息
                if len(msg_chunk.content) > 0:
                    res: str = msg_chunk.content
                    ai_content += res
                    yield SSEMessage(res)
                # 以上是对话信息

    except requests.exceptions.HTTPError as e:
        yield SSEMessage(f"请求失败: {e.response.text}")
    except requests.exceptions.Timeout as e:
        yield SSEMessage(f"请求超时: {e.args[0]}")

    finally:
        all_messages: List[BaseMessage] = agent.get_state(config = get_config(session_id)).values.get("messages", [])

        # 将用户消息持久化
        storage_add_chat(session_id=session_id, role="user", multi_modal_message=multi_modal_message)
        storage_add_chat(session_id=session_id, role="assistant", multi_modal_message=MultiModalMessage(text=ai_content, image_base64_list=None))

        enqueue_append_timeline_entry(session_id = session_id, human_content = multi_modal_message.text, ai_content = ai_content)
        compress_history(session_id = session_id, all_messages = all_messages)

"""以上是返回信息逻辑"""