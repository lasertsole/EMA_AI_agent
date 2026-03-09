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

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None, **kwargs) -> list[str] | None:
        texts = kwargs.get("texts", None)

        if(texts is None):
            raise ValueError("texts is None")
        elif(isinstance(texts, List) == False or any(isinstance(d, str) == False for d in texts)):
            raise TypeError("texts has is type error")
        elif(len(texts) == 0):
            raise ValueError("texts is empty")

        data = {
            "model": model,
            "query": query,  # input类型可为string或string[]。
            "documents": texts
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(data), verify=True)
            res = json.loads(response.text)

            relevant_docs = [
                doc["document"]["text"] for doc in res["results"]
            ]

            return relevant_docs[:self.k]  # 返回前k个结果
        except Exception as e:
            print(e)

class Input(TypedDict):
    query: str
    answers: List[Document]

class GraphState(MessagesState):
    input: Input
    output: List[Document]

def build_rerank_graph(k:int = 10):
    rerank_model = CustomRetriever(k = k)

    def rerank_node(state: GraphState):
        documents: List[Document] = state["input"]["answers"]
        query: str = state["input"]["query"]

        text_doc_dict: TypedDict[str, Document] = {}
        for doc in documents:
            text_doc_dict[doc.page_content] = doc

        texts: List[str] = [key for key in text_doc_dict.keys()]
        texts = rerank_model.invoke(query, texts = texts)

        res = [text_doc_dict[text] for text in texts]
        return { 'output': res }

    workflow = StateGraph(GraphState)

    workflow.add_node("rerank_node", rerank_node)

    workflow.add_edge(START, "rerank_node")
    workflow.add_edge("rerank_node", END)

    graph = workflow.compile()

    return graph