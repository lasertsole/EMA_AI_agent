from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from models import chat_model

# HyDE document genration
template = """Please write a scientific paper passage to answer the question
Question: {question}
Passage:"""
prompt_hyde = ChatPromptTemplate.from_template(template)



generate_docs_for_retrieval = (
    prompt_hyde | chat_model.bind(temperature = 0) | StrOutputParser()
)

async def HyDE(question: str):
    return await generate_docs_for_retrieval.ainvoke({"question":question})