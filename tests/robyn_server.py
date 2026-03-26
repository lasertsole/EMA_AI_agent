import json
from typing import Any

from robyn import Robyn, WebSocketDisconnect
from config import api_host, api_post

#"""以上是组织信息列表逻辑"""
app = Robyn(__file__)

async def ws_processor(session_id: str, event:str, content: str | dict[str, Any])->Any:
    pass

@app.websocket("/ws")
async def ws_handler(websocket):
    try:
        while True:
            try:
                msg: str = await websocket.receive_text()
                obj: dict[str, Any] = json.loads(msg)
                session_id: str = obj.get("session_id", None)
                if session_id:
                    continue

                event: str = obj.get("event", None)
                if event:
                    continue

                content: str | dict[str, Any] = obj.get("content", None)
                if content:
                    continue
                print(123)
                res:Any = await ws_processor(session_id=session_id, event=event, content=content)

                await websocket.send_text(json.dumps(res))
            except Exception as e:
                print(e)
    except (WebSocketDisconnect, ConnectionResetError, Exception) as e:
        print(f"Client {websocket.id} disconnected: {e}")

if __name__ == "__main__":
    app.start(host = api_host, port = api_post)