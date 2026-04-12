import json
from typing import Any, TypedDict
from pydantic import BaseModel, Field


class Turn(BaseModel):
    id: str
    session_id: str
    turn_text: str
    embedding: list[float]
    timestamp: int

def to_turn(ori: dict[str, Any])-> Turn:
    return Turn(
        id = ori["id"],
        session_id = ori["session_id"],
        turn_text = ori["turn_text"],
        embedding = json.loads(ori["embedding"]),
        timestamp = ori["timestamp"]
    )