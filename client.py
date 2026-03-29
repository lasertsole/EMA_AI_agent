import re
import json
import base64
import requests
from typing import Any
import streamlit as st
from typing import List
from pathlib import Path
from urllib.parse import urlencode
from type import MultiModalMessage
from typing import AsyncGenerator, Dict
from models import TTS_Request, fetch_TTS_sound
from websocket import WebSocket, create_connection
from streamlit.delta_generator import DeltaGenerator
from streamlit.elements.widgets.chat import ChatInputValue
from streamlit.runtime.uploaded_file_manager import UploadedFile
from config import ROOT_DIR, USER_NAME, ASSISTANT_NAME, API_HOST, API_PORT
from pub_func import ChatStorage as Streamlit_ChatStorage, process_sse_data

# 创建会话ID
session_id = '1'

# 创建streamlit显示容器
st_container: DeltaGenerator = st.container()

# streamlit最大显示对话数
streamlit_chatStorage = Streamlit_ChatStorage(session_id = session_id, chats_maxlen = 20)

#"""以下是创建websocket连接"""
channels: Dict[str, List[str]] = {}
channels_json = Path(ROOT_DIR) / "channels.json"
if channels_json.exists():
    config: dict[str, dict[str, Any]] = json.loads(channels_json.read_text())
    for key, value in config.items():
        channels[key] = value.get("subscribe_ids", [])
    ws_query_params = {
        "session_id": session_id,
        "channel_to_subscribe_ids": json.dumps(channels, ensure_ascii=False),
    }
    ws_query_string = urlencode(ws_query_params, doseq=True)
#"""以上是创建websocket连接"""

#"""以下是工具函数"""
def filter_content_for_tts(content: str) -> str:
    #"""去除多余字符"""
    res = re.sub(r'[（\\(].*?[）\\)]', ' ', content)
    return res
#"""以上是工具函数"""

async def post_agent_astream(request_json: dict[str, Any]) -> AsyncGenerator[str, None]:
    with requests.post(f"http://{API_HOST}:{API_PORT}/astream", stream=True, json=request_json) as response:
        for line in response.iter_lines():
            yield process_sse_data(line)

# streamlit主程序
def main()-> None:

    chat_list: list[dict[str, Any]] = streamlit_chatStorage.get_chats()
    if len(chat_list) == 0:
        hello_chat = dict(role="assistant", content=f"汉娜さん，来茶间聊天吧！")
        chat_list.append(hello_chat)

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

    if user_input_obj:
        _multi_modal_message: MultiModalMessage = MultiModalMessage(text=user_input_obj.text)
        _files: List[UploadedFile] = user_input_obj.files

        # 添加用户消息框UI
        with st_container:
            with st.chat_message(name = "user", avatar = "./src/avatar/user.jpg"):
                st.markdown(f"{USER_NAME}:{_multi_modal_message.text}")

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

        _multi_modal_message.image_base64_list = image_base64_list if len(image_base64_list) > 0 else None

        # 添加AI消息框UI
        with st_container:
            with st.chat_message(name = "assistant", avatar="./src/avatar/assistant.jpg"):

                request_json = dict(
                    session_id = session_id,
                    multi_modal_message = _multi_modal_message.model_dump(),
                    is_stream = True,
                )

                _content = st.write_stream(post_agent_astream(request_json))

                # 去除开头的ASSISTANT_NAME
                _content = _content[len(f"{ASSISTANT_NAME}:"):]

                with st.spinner("正在生成语音..."):
                    # 生成语音,当生成失败时跳过生成
                    try:
                        # 去除多余字符
                        clear_content = filter_content_for_tts(_content)

                        audio_requires = TTS_Request(text=clear_content, text_lang="zh")
                        response = fetch_TTS_sound(audio_requires)
                        if response is not None:
                            st.audio(data=response.content, format="audio/ogg")

                    except Exception as e:
                        pass
# 执行主程序
if __name__ == "__main__":
    main()