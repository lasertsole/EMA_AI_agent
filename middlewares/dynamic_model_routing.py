from typing import List, Any
from langchain.messages import HumanMessage
from models import base_model, reasoner_model, vl_model
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

def _get_last_user(messages):
    """从消息队列中取最近一条用户消息文本（无则返回空串）"""
    text:str = ""
    had_images:bool = False
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            content: List[dict[str, Any]] = m.content
            for c in content:
                if c.get("type", "") == "image_url":
                    had_images = True

                elif c.get("type", "") == "text":
                    text = c["text"] if isinstance(c["text"], str) else ""
            return text, had_images

# 一些“复杂任务”关键词（可按需扩充）
hard_keywords = ("证明", "推理", "推导", "严谨", "规划", "多步骤", "chain of thought", "step-by-step","reason step-by-step", "数学", "逻辑证明", "约束求解")

@wrap_model_call
async def dynamic_model_routing(request: ModelRequest, handler) -> ModelResponse:
    global hard_keywords
    """
    根据对话复杂度动态选择 DeepSeek 模型:
    - 复杂：deepseek-reasoner
    - 简单：deepseek-chat
    """
    messages = request.state.get("messages", [])
    msg_count = len(messages)
    last_user, had_images = _get_last_user(messages)
    last_len = len(last_user)

    # 选择模型
    if had_images:
        request.override(model=vl_model)
    elif (
        msg_count > 12 or
        last_len > 120 or
        any(kw.lower() in last_user.lower() for kw in hard_keywords)
    ):
        # 简单的复杂度启发式:
        # 1) 历史消息较长 2)最近用户输入很长 3) 出现复杂任务关键词
        request.override(model=reasoner_model)
    else:
        request.override(model=base_model)

    # 结果异步返回
    for attempt in range(3):
        try:
            return await handler(request)
        except Exception:
            if attempt == 2:
                raise