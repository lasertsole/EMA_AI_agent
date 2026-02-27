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
import streamlit as st
from typing import Any
from agent import agent
from collections import deque
from dotenv import load_dotenv
from typing import AsyncGenerator
from langchain.messages import AIMessageChunk
from models import TTS_Request, fetchTTSSound
from streamlit_local_storage import LocalStorage

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './.env')
load_dotenv(env_path, override=True)
is_stream = os.getenv("IS_STREAM")

ai_reply_prefix = "橘雪莉:"

async def async_generator(message_list, config)-> AsyncGenerator[str, None]:
    """
    生成AI回复
    """
    if is_stream == 'True':
        yield ai_reply_prefix
        async for chunk in agent.astream({"messages": message_list}, config=config, stream_mode="messages"):
            msg_chunk: AIMessageChunk = chunk[0]
            event_chunk: dict[str, Any] = chunk[1]

            if (isinstance(msg_chunk, AIMessageChunk)
                    and event_chunk.get("langgraph_node") == 'model'
                    and len(msg_chunk.content) > 0):
                yield msg_chunk.content
    else:
        result = await agent.ainvoke({"messages": message_list}, config=config)
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
    localS = LocalStorage()
    chat_history_maxlen = 20
    saved_data = deque(localS.getItem("chat_history"), maxlen=20)

    if saved_data is None:
        saved_data = deque(maxlen=chat_history_maxlen)
        saved_data.append({"role": "assistant", "content": ai_reply_prefix + "汉娜さん，来茶间聊天吧！"})

    for message in saved_data:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    human_input = st.chat_input(
        "请输入对话内容",
        accept_file = True,
        file_type=["png", "jpg", "jpeg"]
    )
    text = human_input.text
    files = human_input.files
    if human_input:
        with st.chat_message("user"):
            content = "远野汉娜:" + text
            st.markdown(content)

            for file in files:
                st.image(file)

            saved_data.append({"role": "user", "content": content})
        
        message_list = [human_input]
        with st.chat_message("assistant"):
            stream = async_generator(message_list, config)
            content = st.write_stream(stream)

            # 生成语音,当生成失败时跳过生成
            try:
                # 去除多余字符
                clear_content = filter_content_for_tts(content)

                audio_requires = TTS_Request(text=clear_content, text_lang = "zh")
                response = fetchTTSSound(audio_requires)
                if response is not None:
                    st.audio(data=response.content, format="audio/ogg")
            except Exception as e:
                pass
            saved_data.append({"role": "assistant", "content": content})

        localS.setItem("chat_history", list(saved_data))