import asyncio
from threading import Thread
from subagent import subagent_manager

"""以下是处理subagent"""
async def process_subagent_notify(task_res: str):
    print(task_res)
"""以上是处理subagent"""

def run() -> None:
    # 从频道管理器获取事件循环，让 心跳服务 和 cron服务 运行在相同的事件循环中
    event_loop = subagent_manager.get_event_loop()

    try:
        event_loop.run_forever()
    except Exception:
        pass

channel_thread: Thread = Thread(target=run, daemon=True)
channel_thread.start()