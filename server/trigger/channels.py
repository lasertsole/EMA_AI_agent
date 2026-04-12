import json
import asyncio
from pathlib import Path
from config import ROOT_DIR
from threading import Thread
from cron import cron_service
from channels import BaseChannel
from type import MultiModalMessage
from channels import channel_manager
from typing import AsyncGenerator, Any
from heartbeat import heartbeat_service
from server.service import async_generator
from bus import InboundMessage, OutboundMessage
from pub_func import string_to_unique_int, process_sse_data

# 启动频道
channel_thread: Thread = Thread(target = lambda: channel_manager.start_all(), daemon = True)
channel_thread.start()

# 启动心跳服务
_heartbeat_thread: Thread = Thread(target=lambda: asyncio.run(heartbeat_service.start()), daemon=True)
_heartbeat_thread.start()

# 启动cron服务
_cron_thread: Thread = Thread(target=lambda: asyncio.run(cron_service.start()), daemon=True)
_cron_thread.start()

"""以下是常规处理频道信息"""
async def process_qq_inbound(message: InboundMessage, channel: BaseChannel) -> None:
    user_input_text: str = message.content
    user_input: MultiModalMessage = MultiModalMessage(text = user_input_text)
    session_id:str = str(string_to_unique_int(message.sender_id))

    ai_reply: str = ""
    stream: AsyncGenerator[str, None] = async_generator(session_id = session_id, multi_modal_message = user_input, is_stream = False)
    async for item in stream:
        ai_reply += process_sse_data(item)

    await channel.send(OutboundMessage(channel="qq", chat_id = message.chat_id, content = ai_reply))

channel_manager.set_inbound_consumer(
    {
        "qq": process_qq_inbound
    }
)
"""以上是常规处理频道信息"""

"""以下是处理心跳事件"""
async def process_heartbeat(task: str) -> str:
    channels_json: Path = Path(ROOT_DIR) / "channels.json"
    res: list[str] = []

    if channels_json.exists():
        channels_configs: dict[str, Any] = json.loads(channels_json.read_text())
        for name, config in channels_configs.items():
            if config.get("heartbeat", False):
                res.append(name)

    print(task)
    return "OK"
heartbeat_service.on_execute = process_heartbeat

heartbeat_service.on_notify = process_heartbeat
"""以上是处理心跳事件"""

"""以下是定时器事件"""
"""以上是定时器事件"""