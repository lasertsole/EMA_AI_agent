import json
import requests
from channels import BaseChannel
from sessions import read_session
from type import MultiModalMessage
from agent import built_agent, ModelType
from langchain.messages import AIMessageChunk
from bus import InboundMessage, OutboundMessage
from runtime import task_queue, channel_manager
from sessions import viking_routing, load_summary
from typing import AsyncGenerator, Any, Dict, Callable
from workspace.prompt_builder import build_system_prompt
from pub_func import get_config, storage_add_chat, string_to_unique_int, process_sse_data
from robyn import Robyn, SSEMessage, SSEResponse, WebSocketDisconnect, WebSocketAdapter
from config import USER_NAME, ASSISTANT_NAME, API_HOST, API_PORT, COMPRESS_THRESHOLD
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage

# 创建agent
agent = built_agent()

# 创建websocket和sessionStatus的关系字典
websocket_id_to_session_id: Dict[str, str] = {}

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
async def _async_generator(session_id: str, history: list[dict[str, Any]], multi_modal_message: MultiModalMessage, is_stream: bool = True)-> AsyncGenerator[str, None]:
    global current_tool_name
    global current_tool_id

    # 创建消息队列
    messages: list[BaseMessage] = _to_messages(session_id, history, multi_modal_message)
    messages_dict = {"messages": messages}

    try:
        if is_stream:
            yield SSEMessage(f"{ASSISTANT_NAME}:")
            async for chunk in agent.astream(messages_dict, config = get_config(session_id), stream_mode = "messages"):
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
            result = await agent.ainvoke(messages_dict, config = get_config(session_id))
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

    multi_modal_message:MultiModalMessage = request_json.get("multi_modal_message", None)
    if not multi_modal_message:
        return SSEMessage("请提供用户输入")
    multi_modal_message = MultiModalMessage(**multi_modal_message)

    history:list[dict[str, Any]] = read_session(session_id)
    return SSEResponse(_async_generator(session_id, history, multi_modal_message))

"""以下是用websocket维护上下文"""
ws_event_processor_dict: Dict[str, Callable[[str, str | dict[str, Any]], str]] = {}

async def ws_processor(session_id: str, event:str, content: str | dict[str, Any])->Any:
    try:
        processor: Callable[[str, str | dict[str, Any]], str] | None = ws_event_processor_dict.get(event, None)
        if processor is None:
            return None

        return processor(session_id, content)
    except Exception as e:
        print(f"ws_processor error happened: {e}")
        return None

@app.websocket("/ws")
async def ws_handler(websocket: WebSocketAdapter):
    try:
        while True:
            try:
                msg: str = await websocket.receive_text()
                obj: dict[str, Any] = json.loads(msg)

                session_id: str = obj.get("session_id", None)
                if session_id is None:
                    continue

                event: str | None = obj.get("event", None)
                if event is None:
                    continue

                content: str | dict[str, Any] | None = obj.get("content", None)
                if content is None:
                    continue

                res: Any = await ws_processor(session_id=session_id, event=event, content=content)

                await websocket.send_text(json.dumps(res))

            except Exception as e:
                print(e)
    except (WebSocketDisconnect, ConnectionResetError, Exception) as e:
        print(f"Client {websocket.id} disconnected: {e}")

@ws_handler.on_connect
def on_connect(websocket: WebSocketAdapter):
    print(f"Client {websocket.id} connected")

    query_params = websocket.query_params
    session_id = query_params.get("session_id", None)
    if session_id is None:
        websocket.close()
        websocket_id_to_session_id.pop(websocket.id, None)

    websocket_id_to_session_id[websocket.id] = session_id

@ws_handler.on_close
async def handle_disconnect(websocket: WebSocketAdapter):
    print(f"Client {websocket.id} disconnected")
    websocket_id_to_session_id.pop(websocket.id, None)

def enqueue_append_timeline_entry(session_id: str, content: str | dict[str, Any]) -> str | None:
    human_content = content.get("human_content", None)
    if human_content is None:
        return "human_content is None"

    ai_content = content.get("ai_content", None)
    if ai_content is None:
        return "ai_content is None"

    # 添加viking L0 和 L1 索引
    task_queue.enqueue_append_timeline_entry(
    messages=[HumanMessage(content=human_content), AIMessage(content=ai_content)], session_id=session_id,
    tool_metas=[])

    # 如果达到压缩阈值，则压缩历史会话
    total_chars = sum(len(getattr(m, "content", "")) for m in agent.get_state(config = get_config(session_id)).values.get("messages", []))
    if total_chars > COMPRESS_THRESHOLD and task_queue:
        task_queue.enqueue_compress(session_id)

    return "ok"

ws_event_processor_dict["enqueue_append_timeline_entry"] = enqueue_append_timeline_entry
"""以上是用websocket维护上下文"""


async def process_qq_inbound(message: InboundMessage, channel: BaseChannel) -> None:
    user_input_text: str = message.content
    user_input: MultiModalMessage = MultiModalMessage(text=user_input_text)
    session_id:str = str(string_to_unique_int(message.sender_id))

    storage_add_chat(session_id=session_id, chat=dict(role="user", content=user_input_text), name=USER_NAME)

    _history = read_session(session_id)

    ai_reply: str = ""
    async for item in _async_generator(session_id = session_id, history = _history, multi_modal_message = user_input, is_stream=False):
        ai_reply += process_sse_data(item)
    await channel.send(OutboundMessage(channel="qq", chat_id=message.chat_id, content=ai_reply))
    storage_add_chat(session_id=session_id, name=ASSISTANT_NAME, chat=dict(role="assistant", content=ai_reply))


channel_manager.set_inbound_consumer(
    {
        "qq": process_qq_inbound
    }
)
if __name__ == "__main__":
    app.start(host = API_HOST, port = API_PORT)