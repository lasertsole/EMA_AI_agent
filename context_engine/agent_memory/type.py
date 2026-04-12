import json
from typing import Any
from pydantic import BaseModel

class History(BaseModel):
    id: str
    session_id: str
    turn_text: str
    embedding: list[float]
    timestamp: int

def to_history(ori: dict[str, Any])-> History:
    return History(
        id = ori["id"],
        session_id = ori["session_id"],
        turn_text = ori["turn_text"],
        embedding = json.loads(ori["embedding"]),
        timestamp = ori["timestamp"]
    )