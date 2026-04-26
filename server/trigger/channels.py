import asyncio
from threading import Thread
from cron import cron_service
from typing import AsyncGenerator
from type import MultiModalMessage
from heartbeat import heartbeat_service
from server.service import async_generator
from bus import InboundMessage, OutboundMessage
from channels import BaseChannel, channel_manager
from pub_func import string_to_unique_int, process_sse_data
from ..service import process_heartbeat_task, process_heartbeat_notify


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

# 设置频道的消费者
channel_manager.set_inbound_consumer(
    {
        "qq": process_qq_inbound
    }
)
"""以上是常规处理频道信息"""

"""以下是处理心跳事件"""
async def _process_heartbeat_task(task: str) -> str:
    return await process_heartbeat_task(task=task)

heartbeat_service.on_execute = _process_heartbeat_task

async def _process_heartbeat_notify(agent_res: str) -> None:
    return await process_heartbeat_notify(agent_res)

heartbeat_service.on_notify = _process_heartbeat_notify
"""以上是处理心跳事件"""

def run() -> None:
    # 从频道管理器获取事件循环，让 心跳服务 和 cron服务 运行在相同的事件循环中
    event_loop = channel_manager.get_event_loop()

    # 启动心跳服务
    asyncio.run_coroutine_threadsafe(heartbeat_service.start(), event_loop)
    # 启动 cron 服务
    asyncio.run_coroutine_threadsafe(cron_service.start(), event_loop)
    # 启动频道管理器（内部会调用 run_forever）
    channel_manager.start_service()

    try:
        event_loop.run_forever()
    except Exception:
        pass


channel_thread: Thread = Thread(target=run, daemon=True)
channel_thread.start()