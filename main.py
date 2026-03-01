"""
AI 聊天机器人 - Streamlit 异步实现
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
from typing import Any
import streamlit as st
from agent import agent
from pathlib import Path
from dotenv import load_dotenv
from typing import AsyncGenerator
from utils import Chat, File, FileType, ChatStorage
from langchain.messages import AIMessageChunk
from models import TTS_Request, fetchTTSSound

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './.env')
load_dotenv(env_path, override=True)
is_stream = os.getenv("IS_STREAM")

ai_reply_prefix = "橘雪莉:"
chat_storage = ChatStorage(chats_maxlen = 20)

async def async_generator(text, config)-> AsyncGenerator[str, None]:
    """
    生成AI回复
    """
    if is_stream == 'True':
        yield ai_reply_prefix
        async for chunk in agent.astream({"messages": [text]}, config=config, stream_mode="messages"):
            msg_chunk: AIMessageChunk = chunk[0]
            event_chunk: dict[str, Any] = chunk[1]

            if (isinstance(msg_chunk, AIMessageChunk)
                    and event_chunk.get("langgraph_node") == 'model'
                    and len(msg_chunk.content) > 0):
                yield msg_chunk.content
    else:
        result = await agent.ainvoke({"messages": [text]}, config=config)
        yield ai_reply_prefix + result["messages"][-1].content

def filter_content_for_tts(content: str) -> str:
    """
    去除多余字符
    """
    res = content[len(ai_reply_prefix):-1]
    res = re.sub(r'[（\(].*?[）\)]', ' ', res)
    return res


if __name__ == "__main__":
    config = {"configurable": {"thread_id": 1}}

    chat_list: list[Chat] = chat_storage.get_chats()
    if len(chat_list) == 0:
        hello_chat = Chat(role="assistant", content = f"{ai_reply_prefix}汉娜さん，来茶间聊天吧！")
        chat_storage.add_chat(hello_chat)
        chat_list.append(hello_chat)

    for chat in chat_list:
        with st.chat_message(chat.role, avatar=f"./src/avatar/{chat.role}.jpg"):
            st.markdown(chat.content)
            if chat.audio_path_list:
                for file_path in chat.audio_path_list:
                    if Path(file_path).exists():
                        with open(file_path, "rb") as f:
                            st.audio(data=f.read(), format="audio/ogg")

    # 用户输入
    human_input = st.chat_input(
        "请输入对话内容",
        accept_file=True,
        file_type=["png", "jpg", "jpeg"],
    )
    if human_input:
        text = human_input.text
        files = human_input.files
        with st.chat_message("user", avatar="./src/avatar/user.jpg"):
            content = "远野汉娜:" + text
            st.markdown(content)

            for file in files:
                st.image(file)

            chat_storage.add_chat(Chat(role="user", content=content))

        with st.chat_message("assistant", avatar="./src/avatar/assistant.jpg"):
            stream = async_generator(text, config)
            content = st.write_stream(stream)

            file: File
            with st.spinner("正在生成语音..."):
                # 生成语音,当生成失败时跳过生成
                try:
                    # 去除多余字符
                    clear_content = filter_content_for_tts(content)

                    audio_requires = TTS_Request(text=clear_content, text_lang = "zh")
                    response = fetchTTSSound(audio_requires)
                    if response is not None:
                        st.audio(data=response.content, format="audio/ogg")
                        file = {"content":response.content, "type":FileType.AUDIO, "extension": '.wav'}
                except Exception as e:
                    pass

            chat_storage.add_chat(Chat(role="assistant", content=content), files=[file])