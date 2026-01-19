from langchain.agents.middleware import SummarizationMiddleware
from models import base_model

# 上下文摘要压缩，用于无限对话
summarization = SummarizationMiddleware(
    model = base_model,
    trigger = ('tokens', 5),#超过3000token触发摘要
    keep = ('messages', 1),#摘要后保留最近10条消息
)