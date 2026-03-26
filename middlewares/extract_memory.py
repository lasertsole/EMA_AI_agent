from typing import Any
from threading import Thread
from config import MEMORY_DIR
from runtime import get_task_queue
from langchain_core.messages import HumanMessage
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