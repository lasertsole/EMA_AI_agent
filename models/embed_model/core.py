import os
from pathlib import Path
from config import ENV_PATH
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings

# 设置 hugging face 为 离线模式
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from sentence_transformers import SentenceTransformer

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
load_dotenv(ENV_PATH, override = True)
api_key = os.getenv("EMBEDDING_API_KEY")
api_name = os.getenv("EMBEDDING_API_NAME")
api_base = os.getenv("EMBEDDING_API_BASE")

model = SentenceTransformer("BAAI/bge-m3", cache_folder= (current_dir / "model_weight").as_posix())


class CustomEmbedding(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """为多个文档生成嵌入向量"""
        # normalize_embeddings=True 可以让余弦相似度计算更准确
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """为单个查询生成嵌入向量"""
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

#生成模型对象
embed_model = CustomEmbedding()