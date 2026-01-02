import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

# 加载环境变量
load_dotenv(override = True)

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
#生成模型对象
basic_model = ChatDeepSeek(#对话模型
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=1.2,
    max_retries = 2
)

#推理模型
reasoner_model = ChatDeepSeek(
    model='deepseek-reasoner',
    api_key= deepseek_api_key,
    temperature=0.7,
    max_retries = 2
)

#消息汇总模型
summary_model = ChatDeepSeek(#对话模型
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=0.6,
    max_retries = 2
)