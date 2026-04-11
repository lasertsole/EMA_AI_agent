import os
from pathlib import Path
from langchain_core.embeddings import Embeddings

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()
model_cache_folder = current_dir / "model_weight"

if model_cache_folder.exists():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

from sentence_transformers import SentenceTransformer

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

model_cache_folder = current_dir / "model_weight"
model = SentenceTransformer("BAAI/bge-m3", cache_folder= model_cache_folder.as_posix())

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