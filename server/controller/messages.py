import json
from agent import built_agent
from channels import BaseChannel
from sessions import read_session
from type import MultiModalMessage
from runtime import channel_manager
from server.service import async_generator
from config import USER_NAME, ASSISTANT_NAME
from typing import Any, Dict, Callable, List
from bus import InboundMessage, OutboundMessage
from pub_func import storage_add_chat, string_to_unique_int, process_sse_data
from robyn import Robyn, SSEMessage, SSEResponse, WebSocketDisconnect, WebSocketAdapter

# 创建agent
agent = built_agent()

# 创建websocket和sessionStatus的关系字典
websocket_id_to_session_id: Dict[str, str] = {}
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

    history:List[dict[str, Any]] = read_session(session_id)
    return SSEResponse(async_generator(session_id, history, multi_modal_message))

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

"""以上是用websocket维护上下文"""


async def process_qq_inbound(message: InboundMessage, channel: BaseChannel) -> None:
    user_input_text: str = message.content
    user_input: MultiModalMessage = MultiModalMessage(text=user_input_text)
    session_id:str = str(string_to_unique_int(message.sender_id))

    storage_add_chat(session_id=session_id, chat=dict(role="user", content=user_input_text), name=USER_NAME)

    _history = read_session(session_id)

    ai_reply: str = ""
    async for item in async_generator(session_id = session_id, history = _history, multi_modal_message = user_input, is_stream=False):
        ai_reply += process_sse_data(item)
    await channel.send(OutboundMessage(channel="qq", chat_id=message.chat_id, content=ai_reply))
    storage_add_chat(session_id=session_id, name=ASSISTANT_NAME, chat=dict(role="assistant", content=ai_reply))


channel_manager.set_inbound_consumer(
    {
        "qq": process_qq_inbound
    }
)