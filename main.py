import re
import base64
import requests
from typing import Any
import streamlit as st
from typing import List
from pathlib import Path
from pprint import pprint
from channels import BaseChannel
from typing import AsyncGenerator
from type import MultiModalMessage
from threading import Thread, Condition
from agent import built_agent, ModelType
from channels.manager import ChannelManager
from tasks.queue import BackgroundTaskQueue
from langchain.messages import AIMessageChunk
from models import TTS_Request, fetch_TTS_sound
from bus import InboundMessage, OutboundMessage
from config import COMPRESS_THRESHOLD, MEMORY_DIR
from streamlit.delta_generator import DeltaGenerator
from workspace.prompt_builder import build_system_prompt
from graph_memory import sanitize_tool_use_result_pairing
from streamlit.elements.widgets.chat import ChatInputValue
from sessions import read_session, viking_routing, load_summary
from streamlit.runtime.uploaded_file_manager import UploadedFile
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from pub_func import File, FileType, ChatStorage as Streamlit_ChatStorage, storage_add_chat
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage

# 创建会话ID和线程ID
session_id = '1'
thread_id = 1

# 创建配置参数
_config: dict[str, Any] = {"configurable": {"thread_id": thread_id, "model_type": "chat_model"}}

# 创建streamlit显示容器
st_container: DeltaGenerator = st.container()

# streamlit最大显示对话数
streamlit_chatStorage = Streamlit_ChatStorage(session_id = session_id, chats_maxlen = 20)

# 创建线程字典，用于存储多个运行中的线程
@st.cache_resource
def get_thread_dict()-> dict[str, Thread]:
    return {}
thread_dict: dict[str, Thread] = get_thread_dict()

# 创建频道管理器
@st.cache_resource
def get_channel_manager()-> ChannelManager:
    return ChannelManager()
channel_manager:ChannelManager = get_channel_manager()

# 启动频道
if not thread_dict.get("channel_thread"): # 只有线程不存在时才创建和启动，防止僵尸线程
    channel_thread: Thread = Thread(target=lambda: channel_manager.start_all(), daemon=True)
    add_script_run_ctx(channel_thread, get_script_run_ctx()) # 添加脚本运行上下文
    channel_thread.start()
    thread_dict["channel_thread"] = channel_thread

# 创建任务队列
@st.cache_resource
def get_task_queue() -> BackgroundTaskQueue:
    return BackgroundTaskQueue()
task_queue: BackgroundTaskQueue | None = get_task_queue()

# 启动任务队列
if not thread_dict.get("task_queue_thread"): # 只有线程不存在时才创建和启动，防止僵尸线程
    task_queue_thread: Thread = Thread(target=lambda: task_queue.start(), daemon=True)
    task_queue_thread.start()
    thread_dict["task_queue_thread"] = task_queue_thread

# 创建更新页面条件
@st.cache_resource
def get_update_page_condition() -> Condition:
    return Condition()
update_page_condition: Condition = get_update_page_condition()

# 创建agent
agent = built_agent()

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
def _to_messages(history: list[dict[str, Any]], multi_modal_message: MultiModalMessage) -> list[BaseMessage]:
    global agent

    # 使用open-viking路由
    viking_result = viking_routing(session_id = session_id, user_input = multi_modal_message.text)
    files = viking_result.get("file_names", [])
    context = viking_result.get("context", "")

    #"""将历史对话和当前用户输入拼接成消息队列"""
    # 加入系统提示
    messages: list[Any] = [SystemMessage(content = build_system_prompt(selected_file_names = files)+context)]

    # 加入摘要
    summary:str = load_summary(session_id=session_id)
    if summary and len(summary) > 0:
        messages.append(HumanMessage(content=summary))

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

    content_list : list[dict] = [{"type": "text", "text": multi_modal_message.text}]
    if multi_modal_message.image_base64_list:
        for image_base64 in multi_modal_message.image_base64_list:
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
            # 切换模型
            agent = built_agent(model_type = ModelType.VL_MODEL, enable_tool = False)

    messages.append(HumanMessage(content = content_list))
    return messages

#"""以下是组织信息列表逻辑"""
current_tool_name: str = ""
current_tool_id: str = ""
async def _async_generator(history: list[dict[str, Any]], multi_modal_message: MultiModalMessage, config: dict[str, Any], is_stream: bool = True)-> AsyncGenerator[str, None]:
    global current_tool_name
    global current_tool_id

    # 创建消息队列
    messages: list[BaseMessage] = _to_messages(history, multi_modal_message)
    messages_dict = {"messages": messages}

    try:
        if is_stream:
            yield f"{assistant_name}:"
            async for chunk in agent.astream(messages_dict, config = config, stream_mode = "messages"):
                msg_chunk: BaseMessage = chunk[0]
                if isinstance(msg_chunk, AIMessageChunk):
                    # 以下是输出工具信息
                    tool_calls = msg_chunk.tool_calls if msg_chunk.tool_calls and len(msg_chunk.tool_calls) > 0 else msg_chunk.tool_call_chunks
                    if len(tool_calls) > 0 or current_tool_id.strip():
                        repeat_flag: bool = True # 防止重复输出工具信息
                        if len(tool_calls) > 0:
                            tool_call = tool_calls[0]

                            if tool_call["name"]:
                                if tool_call["name"].strip() or tool_call["name"].strip() != current_tool_name:
                                    current_tool_name = tool_call['name']

                            if tool_call["id"]:
                                if tool_call["id"].strip() or tool_call["id"].strip() != current_tool_id:
                                    current_tool_id = tool_call['id']
                                    repeat_flag = False

                        if not repeat_flag:
                            yield f"\n\n**调用工具 {current_tool_name} 中**"

                    if current_tool_id and msg_chunk.content is not None and msg_chunk.content:
                        yield f"\n\n**调用工具 {current_tool_name} 结束。**\n\n"
                        current_tool_id = ""
                    # 以上是输出工具信息

                    # 以下是对话信息
                    if len(msg_chunk.content) > 0:
                        yield msg_chunk.content
                    # 以上是对话信息
        else:
            result = await agent.ainvoke(messages_dict, config = config)
            yield result["messages"][-1].content

    except requests.exceptions.HTTPError as e:
        yield f"请求失败: {e.response.text}"
    except requests.exceptions.Timeout as e:
        yield f"请求超时: {e.args[0]}"
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

        # 将用户要求的知识存入到MEMORY.MD
        memory_entry = _maybe_extract_memory(_multi_modal_message.text)
        if memory_entry:
            _append_memory(memory_entry)
            if task_queue:
                Thread(target=lambda: task_queue.enqueue_memory_index(memory_entry)).start()

        with update_page_condition:
            update_page_condition.notify_all()

        # 添加AI消息框UI
        with st_container:
            with st.chat_message(name = "assistant", avatar="./src/avatar/assistant.jpg"):
                stream = _async_generator(_history, _multi_modal_message, _config)
                _content = st.write_stream(stream)

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
            task_queue.enqueue_append_timeline_entry(
                messages=[HumanMessage(content=_multi_modal_message.text), AIMessage(content=_content)], session_id = session_id,
                tool_metas=[])

            # 如果达到压缩阈值，则压缩历史会话
            total_chars = sum(len(m.get("content", "")) for m in _history) + len(_multi_modal_message.text)
            if total_chars > COMPRESS_THRESHOLD and task_queue:
                task_queue.enqueue_compress(session_id)

        with update_page_condition:
            update_page_condition.notify_all()

    # pprint(sanitize_tool_use_result_pairing(agent.get_state(config=_config).values.get("messages", [])))

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
            async for item in _async_generator(_history, user_input, _config, is_stream=False):
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