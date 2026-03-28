import base64
from typing import Any, List
from tasks.queue import task_queue
from config import COMPRESS_THRESHOLD
from config import USER_NAME, ASSISTANT_NAME
from type import MultiModalMessage, File, FileType
from pub_func import ChatStorage as Streamlit_ChatStorage
from sessions import generate_tsid, append_session_message
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

def enqueue_append_timeline_entry(session_id: str, human_content:str, ai_content: str) -> str | None:
    # 添加viking L0 和 L1 索引
    task_queue.enqueue_append_timeline_entry(
    messages=[HumanMessage(content=human_content), AIMessage(content=ai_content)], session_id=session_id,
    tool_metas=[])

    return "ok"

def compress_history(session_id: str, all_messages: List[BaseMessage]) -> str | None:
    # 如果达到压缩阈值，则压缩历史会话
    total_chars = sum(len(getattr(m, "content", "")) for m in all_messages)
    if total_chars > COMPRESS_THRESHOLD and task_queue:
        task_queue.enqueue_compress(session_id)
    return "ok"

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