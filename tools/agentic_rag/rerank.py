import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import List, TypedDict, Any
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langgraph.graph import StateGraph, START, END, MessagesState

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量和模型初始化（同上）
env_path = current_dir / '../../.env'
env_path = env_path.resolve()
load_dotenv(env_path, override=True)
api_key = os.getenv("EMBEDDING_API_KEY")

# 定义请求基本信息
url = "https://api.modelarts-maas.com/v1/rerank"
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
}
model = "bge-reranker-v2-m3"

# 创建自定义召回model
class CustomRetriever(BaseRetriever):
    k:int = 10

    def __init__(self, k=10, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.k = k

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None, **kwargs) -> list[Document] | None:
        documents = kwargs.get("documents", None)

        if(documents is None):
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
            return relevant_docs[:self.k]  # 返回前k个结果
        except Exception as e:
            print(e)

class Input(TypedDict):
    query: str
    answers: List[str]

class GraphState(MessagesState):
    input: Input
    output: str

def build_rerank_graph(k:int = 10):
    rerank_model = CustomRetriever(k = k)

    def rerank_node(state: GraphState):
        documents: List[Document] = [Document(page_content = answer) for answer in state["input"]["answers"]]
        documents = rerank_model.invoke(state["input"]["query"], documents = documents)
        res = [doc.page_content for doc in documents]

        return { 'output': res }

    workflow = StateGraph(GraphState)

    workflow.add_node("rerank_node", rerank_node)

    workflow.add_edge(START, "rerank_node")
    workflow.add_edge("rerank_node", END)

    graph = workflow.compile()

    return graph