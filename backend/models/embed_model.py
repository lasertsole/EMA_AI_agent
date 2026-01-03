import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(env_path, override = True)
bge_m3 = os.getenv("BGE_M3")

#生成模型对象
embed_model = OpenAIEmbeddings(
    model= 'bge-m3',
    base_url='https://api.modelarts-maas.com/v1',
    api_key = bge_m3
)