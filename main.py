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
import streamlit as st
from typing import Any
from agent import agent
from dotenv import load_dotenv
from typing import AsyncGenerator
from langchain.messages import AIMessageChunk
from models import TTS_Request, fetchTTSSound

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './.env')
load_dotenv(env_path, override=True)
is_stream = os.getenv("IS_STREAM")

async def async_generator(message_list, config)-> AsyncGenerator[str, None]:
    if is_stream == 'True':
        yield "橘雪莉:"
        async for chunk in agent.astream({"messages": message_list}, config=config, stream_mode="messages"):
            msg_chunk: AIMessageChunk = chunk[0]
            event_chunk: dict[str, Any] = chunk[1]

            if (isinstance(msg_chunk, AIMessageChunk)
                    and event_chunk.get("langgraph_node") == 'model'
                    and len(msg_chunk.content) > 0):
                yield msg_chunk.content
    else:
        result = await agent.ainvoke({"messages": message_list}, config=config)
        yield "橘雪莉:" + result["messages"][-1].content


if __name__ == "__main__":
    config = {"configurable": {"thread_id": 1}}

    if "messages" not in st.session_state:
        st.session_state.messages = []

    ai_message = st.chat_message("assistant")
    ai_message.write("橘雪莉:汉娜さん，来茶间聊天吧！")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    human_input = st.chat_input("请输入对话内容")
    if human_input:
        with st.chat_message("user"):
            content = "远野汉娜:" + human_input
            st.markdown(content)
            st.session_state.messages.append({"role": "user", "content": content})
        
        message_list = [human_input]
        with st.chat_message("assistant"):
            stream = async_generator(message_list, config)
            content = st.write_stream(stream)
            st.session_state.messages.append({"role": "assistant", "content": content})

            #生成语音
            audio_requires = TTS_Request(text=content, text_lang = "zh")
            response = fetchTTSSound(audio_requires)
            st.audio(data=response.content, format="audio/ogg")