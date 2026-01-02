import os
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceInferenceAPIEmbedding

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(env_path, override = True)
bge_m3 = os.getenv("BGE_M3")

#生成模型对象
embed_model = HuggingFaceInferenceAPIEmbedding(
    model_name= 'BAAI/bge-m3',
    api_url='https://api.modelarts-maas.com/v1/embeddings',
    api_key = bge_m3,
    normalize = True,# BGE-M3必加
)

# 全局绑定
Settings.embed_model = embed_model