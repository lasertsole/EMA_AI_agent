import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
env_path = current_dir / '../.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
api_key = os.getenv("EMBEDDING_API_KEY")
api_name = os.getenv("EMBEDDING_API_NAME")

#生成模型对象
embed_model = OpenAIEmbeddings(
    model= api_name,
    openai_api_base='https://api.modelarts-maas.com/v1',
    api_key = api_key
)