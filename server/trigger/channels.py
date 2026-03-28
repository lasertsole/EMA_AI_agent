from threading import Thread
from channels import BaseChannel
from sessions import read_session
from typing import AsyncGenerator
from type import MultiModalMessage
from server.service import async_generator
from channels.manager import ChannelManager
from bus import InboundMessage, OutboundMessage
from pub_func import string_to_unique_int, process_sse_data

# 创建频道管理器
channel_manager:ChannelManager = ChannelManager()
# 启动频道
channel_thread: Thread = Thread(target = lambda: channel_manager.start_all(), daemon = True)
channel_thread.start()

async def process_qq_inbound(message: InboundMessage, channel: BaseChannel) -> None:
    user_input_text: str = message.content
    user_input: MultiModalMessage = MultiModalMessage(text = user_input_text)
    session_id:str = str(string_to_unique_int(message.sender_id))

    _history = read_session(session_id)

    ai_reply: str = ""
    stream: AsyncGenerator[str, None] = async_generator(session_id = session_id, history = _history, multi_modal_message = user_input, is_stream = False)
    async for item in stream:
        ai_reply += process_sse_data(item)

    await channel.send(OutboundMessage(channel="qq", chat_id = message.chat_id, content = ai_reply))

channel_manager.set_inbound_consumer(
    {
        "qq": process_qq_inbound
    }
)