import os
import json
import requests
from typing import List
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

# 加载环境变量和模型初始化（同上）
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(env_path, override=True)
api_key = os.getenv("BGE_M3")

# 定义请求基本信息
url = "https://api.modelarts-maas.com/v1/rerank"
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
}
model = "bge-reranker-v2-m3"

# 创建自定义召回model
class CustomRetriever(BaseRetriever):
    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None, **kwargs) -> list[Document] | None:
        k = kwargs.get("k", None)
        documents = kwargs.get("documents", None)

        if(k is None):
            raise ValueError("k is required")
        elif(isinstance(k, int) == False):
            raise TypeError("k must be an integer")
        elif(k < 1):
            raise ValueError("k is invalid")
        elif(documents is None):
            raise ValueError("documents is None")
        elif(isinstance(documents, List) == False or any(isinstance(d, Document) == False for d in documents)):
            raise TypeError("documents has is type error")
        elif(len(documents) == 0):
            raise ValueError("documents is empty")

        data = {
            "model": model,
            "query": query,  # input类型可为string或string[]。
            "documents": [
                doc.page_content for doc in documents
            ]
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), verify=True)
            res = json.loads(response.text)
            relevant_docs = [
                Document(page_content=doc["document"]["text"]) for doc in res["results"]
            ]
            return relevant_docs[:k]  # 返回前k个结果
        except Exception as e:
            print(e)


rerank_model = CustomRetriever()