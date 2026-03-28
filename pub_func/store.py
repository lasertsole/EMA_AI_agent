import base64
from .streamlit import *
from typing import Any, List
from type import MultiModalMessage
from config import USER_NAME, ASSISTANT_NAME
from sessions import generate_tsid, append_session_message
from .streamlit import ChatStorage as Streamlit_ChatStorage

def storage_add_chat(session_id: str, role: str, multi_modal_message: MultiModalMessage):
    name: str = USER_NAME if role == "user" else ASSISTANT_NAME
    content = multi_modal_message.text

    # 初始化聊天记录存储类
    streamlit_ChatStorage = Streamlit_ChatStorage(session_id=session_id, chats_maxlen=20)

    # 生成时间戳
    timestamp = generate_tsid()

    #"""持久化消息"""
    append_session_message(streamlit_ChatStorage.get_session_id(), {"role": role, "content": content, "timestamp": timestamp})

    # 添加聊天记录到显示列表
    files: list[File] = []
    image_base64_list: List[str] = multi_modal_message.image_base64_list
    if image_base64_list is not None:
        for image_base64 in image_base64_list:
            image_bytes = base64.b64decode(image_base64.encode("utf-8"))
            file: File = {"content": image_bytes, "type": FileType.IMAGE, "extension": '.jpg'}
            files.append(file)
    chat: dict[str, Any] = {"role": role, "content": f"{name}:{content}", "timestamp": timestamp}

    streamlit_ChatStorage.add_chat(new_chat= chat, files= files)