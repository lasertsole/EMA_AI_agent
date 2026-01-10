import os.path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from models import embed_model, rerank_model

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
loader = TextLoader("rag_source/allCharacters.txt", encoding="utf-8")
documents = loader.load()

chunks = text_splitter.split_documents(documents)

chunks = [format_chunk(chunk, separators) for chunk in chunks]

indexFolderPath = "./rag_indexDB/backgroundInfo"
if not os.path.exists(indexFolderPath):
    vector_store = FAISS.from_documents(chunks, embedding=embed_model)
    vector_store.save_local(indexFolderPath)

def query_background_info(query:str, k:int) -> List[Document]:
    ### 检验参数 ###
    if (k is None):
        raise ValueError("k is required")
    elif (isinstance(k, int) == False):
        raise TypeError("k must be an integer")
    elif (k < 1):
        raise ValueError("k is invalid")
    elif (query is None):
        raise ValueError("query is None")
    elif (isinstance(query, str) == False):
        raise TypeError("query has is type error")
    elif (len(query) == 0):
        raise ValueError("query is empty")

    ### 召回 ###
    vector_store = FAISS.load_local(embeddings=embed_model, folder_path=indexFolderPath, allow_dangerous_deserialization=True)
    retrieve = vector_store.as_retriever(search_kwargs={'k':k})
    retrieveResults = retrieve.invoke(query)

    ### 重排 ###
    rerankResults = rerank_model.invoke(query, k=k, documents=retrieveResults)
    return rerankResults