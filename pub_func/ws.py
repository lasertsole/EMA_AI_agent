import json
from typing import Any
from websocket import WebSocket

def ws_send(ws: WebSocket, session_id: str, event: str, content: str | dict[str, Any])-> None:
    ws.send(json.dumps({"session_id": session_id, "event": event, "content": content}))