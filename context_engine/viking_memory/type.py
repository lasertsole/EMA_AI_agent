import json
from typing import Any

from pydantic import BaseModel


class Summary(BaseModel):
    id: str
    session_id: str
    summary: str
    embedding: list[float]
    timestamp: int

class Decisions(BaseModel):
    summary_id: str
    session_id: str
    decisions: list[str]
    timestamp: int

class Message(BaseModel):
    summary_id: str
    session_id: str
    turn_text: str
    embedding: list[float]
    timestamp: int

def to_summary(ori: dict[str, Any])-> Summary:
    return Summary(
        id = ori["id"],
        session_id = ori["session_id"],
        summary = ori["summary"],
        embedding = json.loads(ori["embedding"]),
        timestamp = ori["timestamp"]
    )

def to_decisions(ori: dict[str, Any])-> Decisions:
    return Decisions(
        summary_id = ori["summary_id"],
        session_id = ori["session_id"],
        decisions = json.loads(ori["decisions"]),
        timestamp = ori["timestamp"]
    )

def to_message(ori: dict[str, Any])-> Message:
    return Message(
        summary_id = ori["summary_id"],
        session_id = ori["session_id"],
        turn_text = ori["turn_text"],
        embedding = json.loads(ori["embedding"]),
        timestamp = ori["timestamp"]
    )