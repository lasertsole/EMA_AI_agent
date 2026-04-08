import os
from pathlib import Path
from config import ENV_PATH
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
load_dotenv(ENV_PATH, override = True)
api_key = os.getenv("EMBEDDING_API_KEY")
api_name = os.getenv("EMBEDDING_API_NAME")
api_base = os.getenv("EMBEDDING_API_BASE")

#生成模型对象
embed_model = OpenAIEmbeddings(
    model = api_name,
    openai_api_base = api_base,
    api_key = api_key
)