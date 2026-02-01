import os
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
env_path = current_dir / '../../../../.env'
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

# HyDE document genration
template = """Please write a scientific paper passage to answer the question
Question: {question}
Passage:"""
prompt_hyde = ChatPromptTemplate.from_template(template)

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

generate_docs_for_retrieval = (
    prompt_hyde | ChatOpenAI(temperature=0) | StrOutputParser()
)

def HyDE(retriever):
    # Run
    question = "What is task decomposition for LLM agents?"
    generate_docs_for_retrieval.invoke({"question":question})

    # Retrieve
    retrieval_chain = generate_docs_for_retrieval | retriever
    retireved_docs = retrieval_chain.invoke({"question":question})

    # RAG
    template = """Answer the following question based on this context:
    
    {context}
    
    Question: {question}
    """

    prompt = ChatPromptTemplate.from_template(template)

    final_rag_chain = (
        prompt
        | init_chat_model(
            model_provider = model_provider,
            model = api_name,
            api_key = api_key,
            temperature = 0,
            max_retries = 2
        )
        | StrOutputParser()
    )

    final_rag_chain.invoke({"context":retireved_docs,"question":question})