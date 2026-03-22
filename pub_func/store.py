from .streamlit import *
from typing import Any, Optional, List
from sessions import generate_tsid, append_session_message
from .streamlit import ChatStorage as Streamlit_ChatStorage

def storage_add_chat(session_id: str, name: str, chat: dict[str, Any], files: Optional[List[File]] = None):
    if not isinstance(chat["content"], str) or not isinstance(chat["role"], str):
        raise ValueError("Invalid chat")

    # 初始化聊天记录存储类
    streamlit_ChatStorage = Streamlit_ChatStorage(session_id=session_id, chats_maxlen=20)

    # 生成时间戳
    timestamp = generate_tsid()

    #"""持久化消息"""
    append_session_message(streamlit_ChatStorage.get_session_id(), {"role": chat["role"], "content": chat["content"], "timestamp": timestamp})

    # 增加角色前缀
    chat["content"] = f"{name}:{chat['content']}"

    # 增加时间戳
    chat["timestamp"] = timestamp

    # 添加聊天记录到显示列表

    streamlit_ChatStorage.add_chat(new_chat= chat, files= files)