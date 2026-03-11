import os
import re
import asyncio
import threading
from typing import Any

import requests
import streamlit as st
from langchain_core.tools import ToolException
from langgraph.errors import GraphRecursionError

from agent import agent
from pathlib import Path
import concurrent.futures
from dotenv import load_dotenv
from typing import List, Optional
from typing import AsyncGenerator
from asyncio import AbstractEventLoop
from tasks.queue import BackgroundTaskQueue
from langchain.messages import AIMessageChunk
from models import TTS_Request, fetch_TTS_sound
from config import COMPRESS_THRESHOLD, MEMORY_DIR
from workspace.prompt_builder import build_system_prompt
from sessions.history_index import generate_tsid
from sessions.store import append_session_message, read_session
from utils import File, FileType, ChatStorage as Streamlit_ChatStorage
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './.env')
load_dotenv(env_path, override=True)
is_stream = os.getenv("IS_STREAM")

# 创建会话ID和线程ID
session_id = '1'
thread_id = 1

# 创建事件循环
@st.cache_resource
def get_event_loop()->AbstractEventLoop:
    return asyncio.new_event_loop()

# 给asyncio设置事件循环
asyncio.set_event_loop(get_event_loop())

# 创建任务队列
@st.cache_resource
def get_task_queue() -> BackgroundTaskQueue:
    return BackgroundTaskQueue(get_event_loop())

# 启动任务队列
task_queue: BackgroundTaskQueue | None = get_task_queue()
executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
threading.Thread(target= lambda: task_queue.start(), daemon=True).start()

# streamlit最大显示对话数
streamlit_chatStorage = Streamlit_ChatStorage(session_id = session_id, chats_maxlen = 20)

user_name = "远野汉娜"
assistant_name = "橘雪莉"



#"""以下是主动记忆功能"""
def _maybe_extract_memory(text: str) -> str | None:
    keywords = ["请记住", "记住这个", "记下来", "保存到记忆", "write to memory"]
    source = text.strip()
    for kw in keywords:
        if kw in source:
            after = source.split(kw, 1)[1].strip()
            if after.startswith("：") or after.startswith(":"):
                after = after[1:].strip()
            return after if after else source
    return None

def _append_memory(entry: str) -> None:
    path = MEMORY_DIR / "MEMORY.md"

    # 确保文件存在
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.write_text("# MEMORY\n", encoding="utf-8")
    content = path.read_text(encoding="utf-8").rstrip()
    updated = f"{content}\n\n{entry}\n"
    path.write_text(updated, encoding="utf-8")
#"""以上是主动记忆功能"""



#"""以下是组织信息列表逻辑"""
def _to_messages(history: list[dict[str, Any]], user_input: str) -> list[BaseMessage]:
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
    messages.append(HumanMessage(content = user_input))
    return messages

async def _async_generator(history: list[dict[str, Any]], user_input: str, config: dict[str, Any])-> AsyncGenerator[str, None]:
    # 创建消息队列
    messages: list[BaseMessage] = _to_messages(history, user_input)
    # 插入系统提示词
    messages.insert(0, SystemMessage(content=build_system_prompt()))
    messages_dict = {"messages": messages}

    try:
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
    except requests.exceptions.HTTPError as e:
        yield f"请求失败: {e.response.text}"
    except requests.exceptions.Timeout as e:
        yield f"请求超时: {e.args[0]}"
    except GraphRecursionError as e:
        yield f"工具调用循环、超过限制: {e.args[0]}"
    except ToolException as e:
        yield f"调用工具时发生错误: {e.args[0]}"

def _storage_add_chat(chat: dict[str, Any], files: Optional[List[File]] = None):
    if not isinstance(chat["content"], str) or not isinstance(chat["role"], str):
        raise ValueError("Invalid chat")

    # 生成时间戳
    timestamp = generate_tsid()

    #"""持久化消息"""
    append_session_message(session_id, {"role": chat["role"], "content": chat["content"], "timestamp": timestamp})

    # 增加角色前缀
    print(chat)
    if chat["role"] == "assistant":
        chat["content"] = f"{assistant_name}:{chat['content']}"
    elif chat["role"] == "user":
        chat["content"] = f"{user_name}:{chat['content']}"

    chat["timestamp"] = timestamp

    streamlit_chatStorage.add_chat(chat, files)
#"""以上是组织信息列表逻辑"""


#"""以下是工具函数"""
def filter_content_for_tts(content: str) -> str:
    #"""
    #去除多余字符
    #"""
    res = re.sub(r'[（\\(].*?[）\\)]', ' ', content)
    return res
#"""以上是工具函数"""

# streamlit主程序
if __name__ == "__main__":
    _config: dict[str, Any] = {"configurable": {"thread_id": thread_id }}
    _history = read_session(session_id)

    chat_list: list[dict[str, Any]] = streamlit_chatStorage.get_chats()
    if len(chat_list) == 0:
        hello_chat = dict(role="assistant", content = f"汉娜さん，来茶间聊天吧！")
        chat_list.append(hello_chat)
        _storage_add_chat(hello_chat)

    # 创建历史聊天消息UI列表
    for _chat in chat_list:
        with st.chat_message(_chat["role"], avatar=f"./src/avatar/{_chat["role"]}.jpg"):
            st.markdown(_chat["content"])
            if _chat["audio_path_list"]:
                for file_path in _chat["audio_path_list"]:
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
        _user_input = user_input_obj.text
        _files = user_input_obj.files
        
        # 添加用户消息框UI
        with st.chat_message("user", avatar="./src/avatar/user.jpg"):
            st.markdown(f"{user_name}:{_user_input}")

            for _file in _files:
                st.image(_file)

            _storage_add_chat(dict(role="user", content=_user_input))

        # 将用户要求的知识存入到MEMORY.MD
        memory_entry = _maybe_extract_memory(_user_input)
        if memory_entry:
            _append_memory(memory_entry)
            if task_queue:
                asyncio.create_task(task_queue.enqueue_memory_index(memory_entry))

        # 如果达到压缩阈值，则压缩历史会话
        total_chars = sum(len(m.get("content", "")) for m in _history) + len(_user_input)
        if total_chars > COMPRESS_THRESHOLD and task_queue:
            asyncio.run_coroutine_threadsafe(task_queue.enqueue_compress(session_id), get_event_loop())

        # 添加AI消息框UI
        with st.chat_message("assistant", avatar="./src/avatar/assistant.jpg"):
            stream = _async_generator(_history, _user_input, _config)
            _content = st.write_stream(stream)

            # 去除开头的assistant_name
            _content = _content[len(f"{assistant_name}:"):]

            file: File = None
            with st.spinner("正在生成语音..."):
                # 生成语音,当生成失败时跳过生成
                try:
                    # 去除多余字符
                    clear_content = filter_content_for_tts(_content)

                    audio_requires = TTS_Request(text=clear_content, text_lang = "zh")
                    response = fetch_TTS_sound(audio_requires)
                    if response is not None:
                        st.audio(data = response.content, format="audio/ogg")
                        file = {"content":response.content, "type":FileType.AUDIO, "extension": '.wav'}
                except Exception as e:
                    pass

            # 将消息持久化
            _storage_add_chat(dict(role = "assistant", content = _content), files = [file] if file is not None else None)