import json
import os
from typing import List
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.docstore import InMemoryDocstore
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import pickle
from models import embed_model
from langchain_core.documents import Document
from langchain.chat_models import init_chat_model
from langchain_core.stores import InMemoryByteStore
from langchain_classic.retrievers import MultiVectorRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.tools import Tool

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../.env')
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

current_dir = Path(__file__).parent.resolve()

#生成摘要模型对象
summarize_model = init_chat_model(
    model_provider = model_provider,
    model = api_name,
    api_key = api_key,
    temperature = 0.8,
    max_retries = 2
)

# 生成摘要工具链
summarize_chain = (
    {"doc": lambda x: x.page_content}
    | ChatPromptTemplate.from_template("Summarize the following document:\n\n{doc}")
    | summarize_model
    | StrOutputParser()
)

# 如果output文件已存在，则不重复持久化
indexFolderPath = current_dir / "output"
if not indexFolderPath.exists():
    separators = ["\n\n\n"]

    def format_doc(doc: Document, separators: list) -> Document:
        for sep in separators:
            doc.page_content = doc.page_content.strip(sep).strip()
        return doc

    text_splitter = RecursiveCharacterTextSplitter(
        separators = separators,
        is_separator_regex = False,
        doc_size = 1,
        doc_overlap = 0
    )

    info_path = current_dir / "input/allCharacters.txt"

    loader = TextLoader(info_path, encoding="utf-8")
    documents = loader.load()

    docs = text_splitter.split_documents(documents)

    docs = [format_doc(doc, separators) for doc in docs]

    # 将生成的摘要插入文档的metadata中summaries属性
    for doc in docs:
        # 批量生成摘要
        summaries = summarize_chain.batch(docs, {"max_concurrency": 5})
        doc.metadata["summaries"] = summaries

    vector_store = FAISS.from_documents(docs, embedding = embed_model)
    vector_store.save_local(indexFolderPath.as_posix())

# else:
#     docsPath = indexFolderPath / "index.pkl"
#     docsPath = docsPath.as_posix()
#     with open(docsPath, "rb") as f:
#         pkl = pickle.load(f)
#         docs:InMemoryDocstore = pkl[0]
#         print(json.dumps(docs, indent=4))

k:int = 10

### 召回 ###
vector_store = FAISS.load_local(
    embeddings = embed_model,
    folder_path = indexFolderPath.as_posix(),
    allow_dangerous_deserialization = True
)

# store = InMemoryByteStore()
# id_key = "doc_id"

# retriever = MultiVectorRetriever(
#     vectorstore = vector_store,
#     byte_store = store,
#     id_key = id_key,
# )
retriever = vector_store.as_retriever(
    search_type = "similarity_score_threshold",
    search_kwargs = {
        'k' : k,
        'score_threshold' : 0.5
    }
)

def _query_background_info(query:str) -> List[str]:
    ### 检验参数 ###
    if (query is None):
        raise ValueError("query is None")
    elif (isinstance(query, str) == False):
        raise TypeError("query has is type error")
    elif (len(query) == 0):
        raise ValueError("query is empty")

    documents = retriever.invoke(query)

    retrieveResults = [doc.page_content for doc in documents]
    return retrieveResults

#query_background_info = Tool(name="query_background_info", func=_query_background_info, description="""当需要回答 魔法少女的魔女审批 有关知识时调用此工具，
# 输入为具体问题，输出为知识库检索到的答案""")