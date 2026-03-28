from threading import Thread
from channels.manager import ChannelManager
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from tasks.queue import BackgroundTaskQueue


# 创建线程字典，用于存储多个运行中的线程
thread_dict = {}

# 启动任务队列
task_queue: BackgroundTaskQueue = BackgroundTaskQueue()
task_queue_thread: Thread = Thread(target=lambda: task_queue.start(), daemon=True)
task_queue_thread.start()
thread_dict["task_queue_thread"] = task_queue_thread

# 创建频道管理器
channel_manager:ChannelManager = ChannelManager()
# 启动频道
if not thread_dict.get("channel_thread"): # 只有线程不存在时才创建和启动，防止僵尸线程
    channel_thread: Thread = Thread(target=lambda: channel_manager.start_all(), daemon=True)
    add_script_run_ctx(channel_thread, get_script_run_ctx()) # 添加脚本运行上下文
    channel_thread.start()
    thread_dict["channel_thread"] = channel_thread