import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

# 加载环境变量
load_dotenv(override = True)

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

#消息汇总模型
summary_model = ChatDeepSeek(#对话模型
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=0.6,
    max_retries = 2
)