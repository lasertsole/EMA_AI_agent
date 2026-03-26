from config import MEMORY_DIR
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
from streamlit.elements.widgets.chat import ChatInputValue
from sessions import read_session, viking_routing, load_summary
from streamlit.runtime.uploaded_file_manager import UploadedFile
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from pub_func import File, FileType, ChatStorage as Streamlit_ChatStorage, storage_add_chat
from runtime import get_thread_dict, get_channel_manager, get_task_queue, get_update_page_condition
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage, BaseMessage
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse


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

@wrap_model_call
async def extract_memory(request: ModelRequest, handler) -> ModelResponse:
    messages = request.state.get("messages", [])
    if messages and len(messages) > 0 and isinstance(messages[-1], HumanMessage):
        user_input_content:dict[str, Any] = getattr(messages[-1], "content", [])
        usr_input_text:str = ""
        for item in user_input_content:
            if item.get("type", "") == "text":
                usr_input_text += item.get("text", "")
                break

        if usr_input_text:
            memory_entry = _maybe_extract_memory(usr_input_text)
            if memory_entry:
                _append_memory(memory_entry)
                if get_task_queue():
                    Thread(target=lambda: get_task_queue().enqueue_memory_index(memory_entry)).start()

    return await handler(request)