"""
橘雪莉 聊天机器人 - Streamlit 异步实现
===============================
功能：
    1. 基于 langchain agent 实现多轮对话
    2. 支持流式回复（astream）和非流式回复（ainvoke）
    3. 会话状态管理（保存历史聊天记录）
使用方式：
    $  python -m streamlit run main.py
"""
import os
import re
import asyncio
from typing import Any
import streamlit as st
from agent import agent
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional
from typing import AsyncGenerator
from tasks.queue import BackgroundTaskQueue
from utils import Chat, File, FileType, ChatStorage as Streamlit_ChatStorage
from langchain.messages import AIMessageChunk
from models import TTS_Request, fetchTTSSound
from sessions.store import append_session_message,read_session
from config import COMPRESS_THRESHOLD
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './.env')
load_dotenv(env_path, override=True)
is_stream = os.getenv("IS_STREAM")

# 创建会话ID和线程ID
session_id = '1'
thread_id = 1

# 创建任务队列
task_queue: BackgroundTaskQueue | None = BackgroundTaskQueue()
# streamlit最大显示对话数
streamlit_chatStorage = Streamlit_ChatStorage(session_id = session_id,chats_maxlen = 20)

user_name = "远野汉娜"
assistant_name = "橘雪莉"

def _to_messages(history: list[dict[str, Any]], user_input: str) -> list[Any]:
    """将历史对话和当前用户输入拼接成消息队列"""
    messages: list[Any] = []
    for m in history:
        role = m.get("role")
        if role == "user":
            messages.append(HumanMessage(content=m.get("content", "")))
        elif role == "assistant":
            messages.append(AIMessage(content=m.get("content", "")))
        elif role == "tool":
            messages.append(
                ToolMessage(
                    content=m.get("content", ""),
                    tool_call_id=m.get("tool_call_id", ""),
                )
            )
    messages.append(HumanMessage(content=user_input))
    return messages

async def async_generator(user_input, config)-> AsyncGenerator[str, None]:
    """生成AI回复"""
    messages_dict = {"messages": _to_messages(history, user_input)}
    if is_stream == 'True':
        yield f"{assistant_name}:"
        async for chunk in agent.astream(messages_dict, config=config, stream_mode="messages"):
            msg_chunk: AIMessageChunk = chunk[0]
            event_chunk: dict[str, Any] = chunk[1]

            if (isinstance(msg_chunk, AIMessageChunk)
                    and event_chunk.get("langgraph_node") == 'model'
                    and len(msg_chunk.content) > 0):
                yield msg_chunk.content
    else:
        result = await agent.ainvoke(messages_dict, config=config)
        yield result["messages"][-1].content

def add_chat(chat: Chat, files: Optional[List[File]] = None):
    """持久化消息"""
    append_session_message(session_id, {"role": chat.role, "content": chat.content})

    # 增加角色前缀
    if chat.role == "assistant":
        chat.content = f"{assistant_name}:{chat.content}"
    elif chat.role == "user":
        chat.content = f"{user_name}:{chat.content}"

    streamlit_chatStorage.add_chat(chat, files)

def filter_content_for_tts(content: str) -> str:
    """
    去除多余字符
    """
    res = re.sub(r'[（\(].*?[）\)]', ' ', content)
    return res


if __name__ == "__main__":
    config = {"configurable": {"thread_id": thread_id}}
    history = read_session(session_id)

    chat_list: list[Chat] = streamlit_chatStorage.get_chats()
    if len(chat_list) == 0:
        hello_chat = Chat(role="assistant", content = f"汉娜さん，来茶间聊天吧！")
        chat_list.append(hello_chat)
        add_chat(hello_chat)


    for chat in chat_list:
        with st.chat_message(chat.role, avatar=f"./src/avatar/{chat.role}.jpg"):
            st.markdown(chat.content)
            if chat.audio_path_list:
                for file_path in chat.audio_path_list:
                    if Path(file_path).exists():
                        with open(file_path, "rb") as f:
                            st.audio(data=f.read(), format="audio/ogg")

    # 用户输入
    user_input_obj = st.chat_input(
        "请输入对话内容",
        accept_file=True,
        file_type=["png", "jpg", "jpeg"],
    )
    if user_input_obj:
        user_input = user_input_obj.text
        files = user_input_obj.files
        with st.chat_message("user", avatar="./src/avatar/user.jpg"):
            st.markdown(f"{user_name}:{user_input}")

            for file in files:
                st.image(file)

            add_chat(Chat(role="user", content=user_input))

        # 如果达到压缩阈值，则压缩历史会话
        total_chars = sum(len(m.get("content", "")) for m in history) + len(user_input)
        if total_chars > COMPRESS_THRESHOLD and task_queue:
            asyncio.create_task(task_queue.enqueue_compress(session_id))

        with st.chat_message("assistant", avatar="./src/avatar/assistant.jpg"):
            stream = async_generator(user_input, config)
            content = st.write_stream(stream)

            # 去除开头的assistant_name
            content = content[len(f"{assistant_name}:"):-1]

            file: File = None
            with st.spinner("正在生成语音..."):
                # 生成语音,当生成失败时跳过生成
                try:
                    # 去除多余字符
                    clear_content = filter_content_for_tts(content)

                    audio_requires = TTS_Request(text=clear_content, text_lang = "zh")
                    response = fetchTTSSound(audio_requires)
                    if response is not None:
                        st.audio(data = response.content, format="audio/ogg")
                        file = {"content":response.content, "type":FileType.AUDIO, "extension": '.wav'}
                except Exception as e:
                    pass

            add_chat(Chat(role = "assistant", content = content), files = [file] if file is not None else None)