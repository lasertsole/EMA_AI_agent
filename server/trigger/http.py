from agent import built_agent
from sessions import read_session
from type import MultiModalMessage
from server.service import async_generator
from typing import Any, Dict, List
from robyn import Robyn, SSEMessage, SSEResponse

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