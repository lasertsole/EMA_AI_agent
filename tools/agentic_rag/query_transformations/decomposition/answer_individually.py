import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Callable, Awaitable, TypedDict
from langchain_core.output_parsers import StrOutputParser

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
env_path = current_dir / '../../../../.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

# Prompt
template = """
你是一个问答助手，请根据上下文回答问题:
上下文: {context}
问题: {question}
"""

prompt = ChatPromptTemplate.from_template(template)

llm = init_chat_model(
    model_provider = model_provider,
    model = api_name,
    api_key = api_key,
    temperature = 0,
    max_retries = 2
)


def format_qa_pairs(questions: List[str], answers: List[str]):
    """Format Q and A pairs"""

    formatted_string = ""
    for i, (question, answer) in enumerate(zip(questions, answers), start=1):
        formatted_string += f"Question {i}: {question}\nAnswer {i}: {answer}\n\n"
    return formatted_string.strip()

class Input(TypedDict):
    question: str
    sub_questions: List[str]

class GraphState(TypedDict):
    input: Input  # 原问题和子问题列表
    output: str  # 回答

def build_answer_individually_graph(retrieve_callback: Callable[[str], Awaitable[List[Document]]]):
    async def retrieve_and_rag(sub_questions: List[str])-> List[str]:
        """RAG on each sub-question"""

        # Initialize a list to hold RAG chain results
        rag_results = []

        for sub_question in sub_questions:
            # Retrieve documents for each sub-question
            retrieved_docs = await retrieve_callback(sub_question)

            # Use retrieved documents and sub-question in RAG chain
            answer = (prompt | llm | StrOutputParser()).invoke({"context": retrieved_docs,
                                                                    "question": sub_question})
            rag_results.append(answer)

        return rag_results

    async def answer_individually(state: GraphState):
        question = state["input"]["question"]
        sub_questions = state["input"]["sub_questions"]

        answers = await retrieve_and_rag(sub_questions)
        context = format_qa_pairs(sub_questions, answers)

        # Prompt
        template = """Here is a set of Q+A pairs:
        
        {context}
        
        Use these to synthesize an answer to the question: {question}
        """

        prompt = ChatPromptTemplate.from_template(template)

        final_rag_chain = (
                prompt
                | llm
                | StrOutputParser()
        )

        res = await final_rag_chain.ainvoke({"context": context, "question": question})
        return {"output": res}

    workflow = StateGraph(GraphState)

    workflow.add_node("answer_individually_node", answer_individually)

    workflow.add_edge(START, "answer_individually_node")
    workflow.add_edge("answer_individually_node", END)

    answer_individually_graph = workflow.compile()
    return answer_individually_graph