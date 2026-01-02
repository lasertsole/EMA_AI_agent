from langchain.messages import HumanMessage
from models import basic_model, reasoner_model
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

def _get_last_user_text(messages) -> str:
    """从消息队列中取最近一条用户消息文本（无则返回空串）"""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else ""
    return ""

@wrap_model_call
def dynamic_model_routing(request: ModelRequest, handler) -> ModelResponse:
    """
    根据对话复杂度动态选择 DeepSeek 模型:
    - 复杂：deepseek-reasoner
    - 简单：deepseek-chat
    """
    messages = request.state.get("messages", [])
    msg_count = len(messages)
    last_user = _get_last_user_text(messages)
    last_len = len(last_user)

    # 一些“复杂任务”关键词（可按需扩充）
    hard_keywords = ("证明", "推导", "严谨", "规划", "多步骤", "chain of thought", "step-by-step","reason step-by-step", "数学", "逻辑证明", "约束求解")

    # 简单的复杂度启发式:
    # 1) 历史消息较长 2)最近用户输入很长 3) 出现复杂任务关键词
    is_hard = (
        msg_count > 10 or
        last_len > 120 or
        any(kw.lower() in last_user.lower() for kw in hard_keywords)
    )

    # 选择模型
    request.override(model=reasoner_model) if is_hard else basic_model

    return handler(request)