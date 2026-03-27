import json
from typing import Any
from websocket import WebSocket

def ws_send(ws: WebSocket, session_id: str, event: str, content: str | dict[str, Any])-> None:
    ws.send(json.dumps({"session_id": session_id, "event": event, "content": content}))

def validate_config(config: dict[str, Any]) -> (bool, str | None):
    configurable: dict[str, Any] | None = config.get("configurable", None)
    if configurable is None:
        return False, "configurable is None"
    elif not isinstance(configurable, dict):
        return False, "configurable is not dict"

    session_id: str | None = configurable.get("session_id", None)
    if session_id is None:
        return False, "session_id is None"

    return True