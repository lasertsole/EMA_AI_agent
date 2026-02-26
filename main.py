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
from dotenv import load_dotenv
from typing import AsyncGenerator
from langchain.messages import AIMessageChunk
from models import TTS_Request, fetchTTSSound
from langchain_core.messages import HumanMessage, AIMessage

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './.env')
load_dotenv(env_path, override=True)
is_stream = os.getenv("IS_STREAM")

ai_reply_prefix = "橘雪莉:"

async def async_generator(message_list, config)-> AsyncGenerator[str, None]:
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


if __name__ == "__main__":
    config = {"configurable": {"thread_id": 1}}

    if 'messages' in agent.get_state(config).values:
        for message in agent.get_state(config).values['messages']:
            if isinstance(message, HumanMessage):
                with st.chat_message("user"):
                    content = "远野汉娜:" + message.content
                    st.markdown(content)

            elif isinstance(message, AIMessage):
                with st.chat_message("assistant"):
                    content = ai_reply_prefix + message.content
                    st.markdown(content)
    else:
        ai_message = st.chat_message("assistant")
        ai_message.write(ai_reply_prefix + "汉娜さん，来茶间聊天吧！")

    human_input = st.chat_input("请输入对话内容")
    if human_input:
        with st.chat_message("user"):
            content = "远野汉娜:" + human_input
            st.markdown(content)
        
        message_list = [human_input]
        with st.chat_message("assistant"):
            stream = async_generator(message_list, config)
            content = st.write_stream(stream)

            # 生成语音,当生成失败时跳过生成
            try:
                # 去除多余字符
                content = content[len(ai_reply_prefix):-1]
                content = re.sub(r'[（\(].*?[）\)]', ' ', content)

                audio_requires = TTS_Request(text=content, text_lang = "zh")
                response = fetchTTSSound(audio_requires)
                if response is not None:
                    st.audio(data=response.content, format="audio/ogg")
            except Exception as e:
                pass