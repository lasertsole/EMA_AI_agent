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

# 使用示例
documents = [
    Document(page_content="咖啡豆的产地主要分布在赤道附近，被称为‘咖啡带’。"),
    Document(page_content="法压壶的步骤：1. 研磨咖啡豆。2. 加入热水。3. 压下压杆。4. 倒入杯中。"),
    Document(page_content="意式浓缩咖啡需要一台高压机器，在9个大气压下快速萃取。"),
    Document(page_content="挑选咖啡豆时，要注意其烘焙日期，新鲜的豆子风味更佳。"),
    Document(page_content="手冲咖啡的技巧：控制水流速度、均匀注水和合适的水温（90-96°C）是关键。"),
]

# 创建自定义召回model
class CustomRetriever(BaseRetriever):
    """一个简单的字符串匹配检索器。"""
    documents: List[Document]  # 要搜索的文档列表
    k: int = 3  # 返回的最大文档数

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None) -> List[Document]:
        query_lower = query.lower()
        data = {
            "model": "bge-reranker-v2-m3",
            "query": "牛是一种动物如何冲泡一杯好喝的咖啡？",  # input类型可为string或string[]。
            "documents": [
                "咖啡豆的产地主要分布在赤道附近，被称为‘咖啡带’。",
                "法压壶的步骤：1. 研磨咖啡豆。2. 加入热水。3. 压下压杆。4. 倒入杯中。",
                "意式浓缩咖啡需要一台高压机器，在9个大气压下快速萃取。",
                "挑选咖啡豆时，要注意其烘焙日期，新鲜的豆子风味更佳。",
                "手冲咖啡的技巧：控制水流速度、均匀注水和合适的水温（90-96°C）是关键。"
            ]
        }
        response = requests.post(url, headers=headers, data=json.dumps(data), verify=False)
        relevant_docs = [
            doc for doc in self.documents
            if query_lower in doc.page_content.lower()
        ]
        return relevant_docs[:self.k]  # 返回前k个结果


rerank_model = CustomRetriever(documents=documents, k=2)
results = rerank_model.invoke("动物")
print(results)
# 输出: [Document(page_content='狗是忠诚的动物'), Document(page_content='猫是独立的动物')]