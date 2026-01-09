from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader

text_splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n\n"],
    is_separator_regex=False,
    chunk_size= 1,
    chunk_overlap=0
)
loader = TextLoader("rag_source/allCharacters.txt", encoding="utf-8")
documents = loader.load()

chunks = text_splitter.split_documents(documents)

for chunk in chunks:
    print(chunk.page_content)