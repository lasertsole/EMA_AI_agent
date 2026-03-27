from pydantic import BaseModel
from channels import BaseChannel
from typing import List, Optional
from robyn import WebSocketAdapter

# 多模态消息体
class MultiModalMessage(BaseModel):
    text: str
    image_base64_list: Optional[List[str]] = None

class ChannelSubscribe(BaseModel):
    channel: BaseChannel
    subscribe_ids: set[str]

class SessionStatus(BaseModel):
    session_id: str
    ws_connection: WebSocketAdapter
    channel_connections: dict[str, ChannelSubscribe]