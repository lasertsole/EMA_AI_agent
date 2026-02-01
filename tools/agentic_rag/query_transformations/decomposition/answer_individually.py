import os
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
env_path = current_dir / '../../../../.env'
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

# # RAG prompt
# prompt_rag = ''''''
#
# llm = init_chat_model(
#     model_provider = model_provider,
#     model = api_name,
#     api_key = api_key,
#     temperature = 0,
#     max_retries = 2
# )
#
# def retrieve_and_rag(question, prompt_rag, sub_question_generator_chain):
#     """RAG on each sub-question"""
#
#     # Use our decomposition /
#     sub_questions = sub_question_generator_chain.invoke({"question": question})
#
#     # Initialize a list to hold RAG chain results
#     rag_results = []
#
#     for sub_question in sub_questions:
#         # Retrieve documents for each sub-question
#         retrieved_docs = retriever.get_relevant_documents(sub_question)
#
#         # Use retrieved documents and sub-question in RAG chain
#         answer = (prompt_rag | llm | StrOutputParser()).invoke({"context": retrieved_docs,
#                                                                 "question": sub_question})
#         rag_results.append(answer)
#
#     return rag_results, sub_questions
#
#
# # Wrap the retrieval and RAG process in a RunnableLambda for integration into a chain
# answers, questions = retrieve_and_rag(question, prompt_rag, generate_queries_decomposition)
#
#
# def format_qa_pairs(questions, answers):
#     """Format Q and A pairs"""
#
#     formatted_string = ""
#     for i, (question, answer) in enumerate(zip(questions, answers), start=1):
#         formatted_string += f"Question {i}: {question}\nAnswer {i}: {answer}\n\n"
#     return formatted_string.strip()
#
#
# context = format_qa_pairs(questions, answers)
#
# # Prompt
# template = """Here is a set of Q+A pairs:
#
# {context}
#
# Use these to synthesize an answer to the question: {question}
# """
#
# prompt = ChatPromptTemplate.from_template(template)
#
# final_rag_chain = (
#         prompt
#         | llm
#         | StrOutputParser()
# )
#
# final_rag_chain.invoke({"context": context, "question": question})