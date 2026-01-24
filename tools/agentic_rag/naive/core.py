from pathlib import Path
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from models import embed_model, rerank_model
from langchain_core.tools import Tool

separators=["\n\n\n"]

def format_chunk(chunk: Document, separators: list) -> Document:
    for sep in separators:
        chunk.page_content = chunk.page_content.strip(sep).strip()
    return chunk


text_splitter = RecursiveCharacterTextSplitter(
    separators=separators,
    is_separator_regex=False,
    chunk_size= 1,
    chunk_overlap=0
)

current_dir = Path(__file__).parent.resolve()
info_path = current_dir / "naive/input/allCharacters.txt"

loader = TextLoader(info_path, encoding="utf-8")
documents = loader.load()

chunks = text_splitter.split_documents(documents)

chunks = [format_chunk(chunk, separators) for chunk in chunks]

indexFolderPath = current_dir / "naive/output"
if not indexFolderPath.exists():
    indexFolderPath=indexFolderPath.as_posix()
    vector_store = FAISS.from_documents(chunks, embedding=embed_model)
    vector_store.save_local(indexFolderPath)

k:int = 3
def _query_background_info(query:str) -> List[Document]:
    ### 检验参数 ###
    if (query is None):
        raise ValueError("query is None")
    elif (isinstance(query, str) == False):
        raise TypeError("query has is type error")
    elif (len(query) == 0):
        raise ValueError("query is empty")

    ### 召回 ###
    vector_store = FAISS.load_local(embeddings=embed_model, folder_path=indexFolderPath, allow_dangerous_deserialization=True)
    retrieve = vector_store.as_retriever(
        search_type = "similarity_score_threshold",
        search_kwargs = {
            'k' : k,
            'score_threshold' : 0.5
        }
    )
    retrieveResults = retrieve.invoke(query)

    ### 重排 ###
    rerankResults = rerank_model.invoke(query, k=k, documents=retrieveResults)
    return rerankResults

query_background_info = Tool(name="query_background_info", func=_query_background_info, description="""当需要回答 魔法少女的魔女审批 有关知识时调用此工具，
输入为具体问题，输出为知识库检索到的答案""")