from threading import Thread
from subagent import subagent_manager

"""以下是处理subagent"""
async def process_subagent_notify(task_res: str):
    print(task_res)
"""以上是处理subagent"""

def run() -> None:
    event_loop = subagent_manager.get_event_loop()

    subagent_manager.start_service()

    try:
        event_loop.run_forever()
    except Exception:
        pass

subagent_thread: Thread = Thread(target=run, daemon=True)
subagent_thread.start()