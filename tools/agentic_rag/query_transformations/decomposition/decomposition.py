from models import chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

template = """You are a helpful assistant that generates multiple sub-questions related to an input question. \n
The goal is to break down the input into a set of sub-problems / sub-questions that can be answers in isolation. \n
Generate multiple search queries related to: {question} \n
Output (3 queries, No numbering.):"""
prompt_decomposition = ChatPromptTemplate.from_template(template)

# Chain
generate_queries_decomposition =  prompt_decomposition | chat_model.bind(temperature = 0) | StrOutputParser() | (lambda x: x.split("\n"))