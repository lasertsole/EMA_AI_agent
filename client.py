import re
import json
import base64
import requests
from typing import Any
import streamlit as st
from typing import List
from pathlib import Path
from channels import BaseChannel
from sessions import read_session
from urllib.parse import urlencode
from type import MultiModalMessage
from typing import AsyncGenerator, Dict
from threading import Thread, Condition
from channels.manager import ChannelManager
from bus import InboundMessage, OutboundMessage
from models import TTS_Request, fetch_TTS_sound
from websocket import WebSocket, create_connection
from streamlit.delta_generator import DeltaGenerator
from streamlit.elements.widgets.chat import ChatInputValue
from streamlit.runtime.uploaded_file_manager import UploadedFile
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from config import ROOT_DIR, user_name, assistant_name, api_host, api_post
from pub_func import File, FileType, ChatStorage as Streamlit_ChatStorage, storage_add_chat, ws_send
from runtime import get_channel_manager, get_update_page_condition

# 创建会话ID
session_id = '1'

# 创建streamlit显示容器
st_container: DeltaGenerator = st.container()

# streamlit最大显示对话数
streamlit_chatStorage = Streamlit_ChatStorage(session_id = session_id, chats_maxlen = 20)

# 创建频道管理器
channel_manager:ChannelManager = get_channel_manager()

"""以下是创建websocket连接"""
channels: List[Dict[str, Any]] = []
channels_json = Path(ROOT_DIR) / "channels.json"
if channels_json.exists():
    config: dict[str, dict[str, Any]] = json.loads(channels_json.read_text())
    for key, value in config.items():
        channels.append({"name": key, "subscribe_ids": value})

    ws_query_params = {
        "session_id": session_id,
        "channels": json.dumps(list, ensure_ascii=False),
    }
    ws_query_string = urlencode(ws_query_params, doseq=True)

@st.cache_resource
def get_ws() -> WebSocket:
    return create_connection(f"ws://{api_host}:{api_post}/ws?{ws_query_string}")
"""以上是创建websocket连接"""

# 创建更新页面条件
update_page_condition: Condition = get_update_page_condition()

#"""以下是工具函数"""
def filter_content_for_tts(content: str) -> str:
    #"""
    #去除多余字符
    #"""
    res = re.sub(r'[（\\(].*?[）\\)]', ' ', content)
    return res
#"""以上是工具函数"""

async def post_agent_astream(request_json: dict[str, Any]) -> AsyncGenerator[str, None]:
    with requests.post(f"http://{api_host}:{api_post}/astream", stream=True, json=request_json) as response:
        for line in response.iter_lines():
            if line:
                decoded_line: str = line.decode()
                if decoded_line.startswith("data: "):
                    content = decoded_line[6:]
                    yield content

# streamlit主程序
def main()-> None:
    _history = read_session(session_id)

    chat_list: list[dict[str, Any]] = streamlit_chatStorage.get_chats()
    if len(chat_list) == 0:
        hello_chat = dict(role="assistant", content=f"汉娜さん，来茶间聊天吧！")
        chat_list.append(hello_chat)
        storage_add_chat(session_id=session_id, name=assistant_name, chat=hello_chat)

    # 创建历史聊天消息UI列表
    with st_container:
        for _chat in chat_list:
            with st.chat_message(_chat["role"], avatar=f"./src/avatar/{_chat['role']}.jpg"):
                st.markdown(_chat["content"])
                if "audio_path_list" in _chat and _chat["audio_path_list"] is not None:
                    for file_path in _chat["audio_path_list"]:
                        if Path(file_path).exists():
                            with open(file_path, "rb") as f:
                                st.audio(data=f.read(), format="audio/ogg")

                if "image_path_list" in _chat and _chat["image_path_list"] is not None:
                    for file_path in _chat["image_path_list"]:
                        if Path(file_path).exists():
                            with open(file_path, "rb") as f:
                                st.image(f.read())

    # 用户输入
    user_input_obj: ChatInputValue = st.chat_input(
        "请输入对话内容",
        accept_file=True,
        file_type=["png", "jpg", "jpeg"],
    )
    # 创建文件列表
    file_list: list[File] = []

    if user_input_obj:
        _multi_modal_message: MultiModalMessage = MultiModalMessage(text=user_input_obj.text)
        _files: List[UploadedFile] = user_input_obj.files

        # 添加用户消息框UI
        with st_container:
            with st.chat_message(name = "user", avatar = "./src/avatar/user.jpg"):
                st.markdown(f"{user_name}:{_multi_modal_message.text}")

        # 遍历用户上传图片文件
        image_base64_list: List[str] = []
        for _file in _files:
            # 显示图片
            st.image(_file)

            # 将图片转为bytes
            file_bytes: bytes = _file.getvalue()

            # 将 图片bytes 放入base64列表
            base64_bytes = base64.b64encode(file_bytes)
            base64_string = base64_bytes.decode("utf-8")
            image_base64_list.append(base64_string)

            # 将 图片bytes 放入文件列表
            file: File = {"content": file_bytes, "type": FileType.IMAGE, "extension": '.jpg'}
            file_list.append(file)
        _multi_modal_message.image_base64_list = image_base64_list if len(image_base64_list) > 0 else None

        # 将用户消息持久化
        storage_add_chat(session_id=session_id, name=user_name, chat=dict(role = "user", content = _multi_modal_message.text), files=file_list if len(file_list) > 0 else None)

        with update_page_condition:
            update_page_condition.notify_all()

        # 添加AI消息框UI
        with st_container:
            with st.chat_message(name = "assistant", avatar="./src/avatar/assistant.jpg"):

                request_json = dict(
                    session_id = session_id,
                    history = _history,
                    multi_modal_message = _multi_modal_message.model_dump(),
                    is_stream = True,
                )

                _content = st.write_stream(post_agent_astream(request_json))

                # 去除开头的assistant_name
                _content = _content[len(f"{assistant_name}:"):]

                # 重置文件列表
                file_list = []

                with st.spinner("正在生成语音..."):
                    # 生成语音,当生成失败时跳过生成
                    try:
                        # 去除多余字符
                        clear_content = filter_content_for_tts(_content)

                        audio_requires = TTS_Request(text=clear_content, text_lang="zh")
                        response = fetch_TTS_sound(audio_requires)
                        if response is not None:
                            st.audio(data=response.content, format="audio/ogg")
                            file: File = {"content": response.content, "type": FileType.AUDIO, "extension": '.wav'}
                            file_list.append(file)
                    except Exception as e:
                        pass

            # 将AI消息持久化
            storage_add_chat(session_id=session_id, name=assistant_name, chat= dict(role="assistant", content=_content), files = file_list if len(file_list) > 0 else None)

            # 添加viking L0 和 L1 索引
            ws_send(ws=get_ws(), session_id=session_id, event="enqueue_append_timeline_entry", content={"human_content": _multi_modal_message.text, "ai_content": _content})


        with update_page_condition:
            update_page_condition.notify_all()

    # 只在页面状态更新时刷新页面，让主程序挂起以便接收到频道信息
    with update_page_condition:
        update_page_condition.wait()
    st.rerun(scope="app")


# 执行主程序
if __name__ == "__main__":
    # 配置频道处理逻辑
    if channel_manager.get_inbound_consumer() is None: # 判断是否已配置过，避免反复配置
        async def process_qq_inbound(message: InboundMessage, channel: BaseChannel) -> None:
            user_input_text: str = message.content
            user_input:MultiModalMessage = MultiModalMessage(text=user_input_text)
            storage_add_chat(session_id=session_id, chat=dict(role="user", content=user_input_text), name=user_name)

            _history = read_session(session_id)

            ai_reply: str = ""
            request_json = dict(
                session_id=session_id,
                history=_history,
                multi_modal_message=user_input,
                is_stream=False,
            )

            async for item in post_agent_astream(request_json):
                ai_reply = item
            await channel.send(OutboundMessage(channel="qq", chat_id=message.chat_id, content=ai_reply))
            storage_add_chat(session_id=session_id, name=assistant_name, chat= dict(role="assistant", content=ai_reply))

            # 更新页面
            with update_page_condition:
                update_page_condition.notify_all()

        channel_manager.set_inbound_consumer(
            {
                "qq": process_qq_inbound
            }
        )

    # 启动主程序
    main_thread:Thread = Thread(target=main())
    add_script_run_ctx(main_thread, get_script_run_ctx())
    main_thread.start()