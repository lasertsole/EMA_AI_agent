from typing import Any

def get_config(session_id: str) -> dict[str, Any]:
    try:
        return {"configurable": {"thread_id": int(session_id)}}
    except ValueError:
        raise Exception("session_id must be an integer")