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
from langgraph.graph.state import CompiledStateGraph
from pub_func import string_to_unique_int, process_sse_data
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage


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
async def process_heartbeat_task(task: str) -> str:
    try:
        from agent import built_agent
        from workspace.prompt_builder import build_system_prompt

        agent: CompiledStateGraph = built_agent(checkpointer = None)
        messages: list[BaseMessage] = [SystemMessage(content=build_system_prompt(selected_file_names=[])), HumanMessage(content=task)]
        result: dict[str, Any] = agent.invoke(input={"messages": messages})

        return result["messages"][-1].content
    except Exception as e:
        return f"发生错误{e}"

heartbeat_service.on_execute = process_heartbeat_task

async def process_heartbeat_notify(agent_res: str) -> None:
    channels_json: Path = Path(ROOT_DIR) / "channels.json"
    res: dict[str, str] = {}

    if channels_json.exists():
        channels_configs: dict[str, Any] = json.loads(channels_json.read_text())
        for name, config in channels_configs.items():
            if config.get("heartbeat", False) and config.get("heartbeat_receiver", False):
                res[name] = config["heartbeat_receiver"]

    for name, receiver in res.items():
        channel: BaseChannel = channel_manager.get_channel(name)
        if channel:
            await channel.send(OutboundMessage(channel=name, chat_id = receiver, content = agent_res))

heartbeat_service.on_notify = process_heartbeat_notify
"""以上是处理心跳事件"""

def run() -> None:
    # 从频道管理器获取事件循环，让 心跳服务 和 cron服务 运行在相同的事件循环中
    event_loop = channel_manager.get_event_loop()

    # 启动心跳服务
    asyncio.run_coroutine_threadsafe(heartbeat_service.start(), event_loop)
    # 启动 cron 服务
    asyncio.run_coroutine_threadsafe(cron_service.start(), event_loop)
    # 启动频道管理器（内部会调用 run_forever）
    channel_manager.start_all()

    try:
        event_loop.run_forever()
    except Exception:
        pass


channel_thread: Thread = Thread(target=run, daemon=True)
channel_thread.start()