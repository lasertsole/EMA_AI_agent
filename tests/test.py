import asyncio
from robyn import Robyn
from threading import Thread
from config import API_HOST, API_PORT
from subagent import subagent_manager

bus = subagent_manager.get_buts()

def main()-> None:
    event_loop = subagent_manager.get_event_loop()

    event_loop.create_task(subagent_manager.spawn(
        "subagent_1",
        "画一个大魔女拯救世界,放在本项目的临时目录./src/temp文件夹里之后，立刻结束并提交工作结果",
        "大魔女救世"
    ))

    subagent_manager.start_service()



if __name__ == "__main__":
    asyncio.run(main())

    channel_thread: Thread = Thread(target=main, daemon=True)
    channel_thread.start()

    # 创建app
    app = Robyn(__file__)
    app.start(host=API_HOST, port=API_PORT)
