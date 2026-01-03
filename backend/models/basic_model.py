import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(env_path, override = True)
api_key = os.getenv("DEEPSEEK_API_KEY")

#生成模型对象
basic_model = ChatDeepSeek(#对话模型
    model='deepseek-chat',
    api_key= api_key,
    temperature=0.8,
    max_retries = 2
)