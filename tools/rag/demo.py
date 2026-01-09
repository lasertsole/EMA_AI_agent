from langchain_text_splitters import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader

text_splitter = CharacterTextSplitter(
    separator="cut-off",
    is_separator_regex=False,
    chunk_overlap=0
)

loader = TextLoader("./rag_source/otherCharacters.txt", encoding="utf-8")
document = loader.load()

chunks = text_splitter.split_documents(document)


print(chunks)