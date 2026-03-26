import requests
from typing import Any
from typing import AsyncGenerator
from type import MultiModalMessage
from agent import built_agent, ModelType
from langchain.messages import AIMessageChunk
from robyn import Robyn, SSEMessage, SSEResponse
from sessions import viking_routing, load_summary
from config import assistant_name, api_host, api_post
from workspace.prompt_builder import build_system_prompt
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage

# 创建agent
agent = built_agent()

#"""以下是组织信息列表逻辑"""
def _to_messages(session_id: str, history: list[dict[str, Any]], multi_modal_message: MultiModalMessage) -> list[BaseMessage]:
    global agent

    # 使用open-viking路由
    viking_result = viking_routing(session_id = session_id, user_input = multi_modal_message.text)
    files = viking_result.get("file_names", [])
    context = viking_result.get("context", "")

    #"""将历史对话和当前用户输入拼接成消息队列"""
    # 加入系统提示
    messages: list[Any] = [SystemMessage(content = build_system_prompt(selected_file_names = files)+context)]

    # 加入摘要
    summary:str = load_summary(session_id=session_id)
    if summary and len(summary) > 0:
        messages.append(HumanMessage(content=summary))

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

    content_list : list[dict] = [{"type": "text", "text": multi_modal_message.text}]
    if multi_modal_message.image_base64_list:
        for image_base64 in multi_modal_message.image_base64_list:
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
            # 切换模型
            agent = built_agent(model_type = ModelType.VL_MODEL, enable_tool = False)

    messages.append(HumanMessage(content = content_list))
    return messages

#"""以下是组织信息列表逻辑"""

#"""以下是组织信息列表逻辑"""
current_tool_name: str = ""
current_tool_id: str = ""
async def _async_generator(session_id: str, history: list[dict[str, Any]], multi_modal_message: MultiModalMessage, config: dict[str, Any], is_stream: bool = True)-> AsyncGenerator[str, None]:
    global current_tool_name
    global current_tool_id

    # 创建消息队列
    messages: list[BaseMessage] = _to_messages(session_id, history, multi_modal_message)
    messages_dict = {"messages": messages}

    try:
        if is_stream:
            yield SSEMessage(f"{assistant_name}:")
            async for chunk in agent.astream(messages_dict, config = config, stream_mode = "messages"):
                msg_chunk: BaseMessage = chunk[0]
                if isinstance(msg_chunk, AIMessageChunk):
                    # 以下是输出工具信息
                    tool_calls = msg_chunk.tool_calls if msg_chunk.tool_calls and len(msg_chunk.tool_calls) > 0 else msg_chunk.tool_call_chunks
                    if len(tool_calls) > 0 or current_tool_id.strip():
                        repeat_flag: bool = True # 防止重复输出工具信息
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
                            yield SSEMessage(f"\n\n**调用工具 {current_tool_name} 中**")

                    if current_tool_id and msg_chunk.content is not None and msg_chunk.content:
                        yield SSEMessage(f"\n\n**调用工具 {current_tool_name} 结束。**\n\n")
                        current_tool_id = ""
                    # 以上是输出工具信息

                    # 以下是对话信息
                    if len(msg_chunk.content) > 0:
                        yield SSEMessage(msg_chunk.content)
                    # 以上是对话信息
        else:
            result = await agent.ainvoke(messages_dict, config = config)
            yield SSEMessage(result["messages"][-1].content)

    except requests.exceptions.HTTPError as e:
        yield SSEMessage(f"请求失败: {e.response.text}")
    except requests.exceptions.Timeout as e:
        yield SSEMessage(f"请求超时: {e.args[0]}")

#"""以上是组织信息列表逻辑"""
app = Robyn(__file__)

@app.post("/astream")
async def stream_async_events(request):
    request_json = request.json()

    session_id:str = request_json.get("session_id", None)
    if not session_id:
        return SSEMessage("请提供会话ID")

    history:list[dict[str, Any]] = request_json.get("history", None)
    if not history:
        return SSEMessage("请提供历史对话")

    multi_modal_message:MultiModalMessage = request_json.get("multi_modal_message", None)
    if not multi_modal_message:
        return SSEMessage("请提供用户输入")
    multi_modal_message = MultiModalMessage(**multi_modal_message)

    config:dict[str, Any] = request_json.get("config", None)
    if not config:
        return SSEMessage("请提供配置")

    return SSEResponse(_async_generator(session_id, history, multi_modal_message, config))

if __name__ == "__main__":
    app.start(host = api_host, port = api_post)