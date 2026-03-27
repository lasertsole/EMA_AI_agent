import streamlit as st
from threading import Thread, Condition
from channels.manager import ChannelManager
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

# 创建线程字典，用于存储多个运行中的线程
@st.cache_resource
def get_thread_dict()-> dict[str, Thread]:
    return {}

# 创建频道管理器
@st.cache_resource
def get_channel_manager()-> ChannelManager:
    return ChannelManager()

# 创建更新页面条件
@st.cache_resource
def get_update_page_condition() -> Condition:
    return Condition()

# 启动频道
if not get_thread_dict().get("channel_thread"): # 只有线程不存在时才创建和启动，防止僵尸线程
    channel_thread: Thread = Thread(target=lambda: get_channel_manager().start_all(), daemon=True)
    add_script_run_ctx(channel_thread, get_script_run_ctx()) # 添加脚本运行上下文
    channel_thread.start()
    get_thread_dict()["channel_thread"] = channel_thread