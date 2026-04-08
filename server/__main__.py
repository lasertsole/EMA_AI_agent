import asyncio
from threading import Thread
from cron import cron_service
from config import API_HOST, API_PORT
from heartbeat import heartbeat_service

if __name__ == "__main__":
    print(f"🚀 服务器启动中... 地址：http://{API_HOST}:{API_PORT}")

    """以下是启动心跳服务"""
    _heartbeat_thread: Thread = Thread(target=lambda: asyncio.run(heartbeat_service.start()), daemon=True)
    _heartbeat_thread.start()
    """以上是启动心跳服务"""

    """以下是启动cron服务"""
    _cron_thread: Thread = Thread(target=lambda: asyncio.run(cron_service.start()), daemon=True)
    _cron_thread.start()
    """以上是启动cron服务"""

    # 导入以注册所有路由和处理器
    from .trigger import app
    app.start(host=API_HOST, port=API_PORT)