from models import base_model
from operator import itemgetter
from langchain_core.documents import Document
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Callable, Awaitable, TypedDict
from langchain_core.output_parsers import StrOutputParser

# Prompt
template = """Here is the question you need to answer:

\n --- \n {question} \n --- \n

Here is any available background question + answer pairs:

\n --- \n {q_a_pairs} \n --- \n

Here is additional context relevant to the question: 

\n --- \n {context} \n --- \n

Use the above context and any background question + answer pairs to answer the question: \n {question}
"""

decomposition_prompt = ChatPromptTemplate.from_template(template)

def format_qa_pair(question, answer):
    """Format Q and A pair"""

    formatted_string = ""
    formatted_string += f"Question: {question}\nAnswer: {answer}\n\n"
    return formatted_string.strip()


# llm
llm = base_model.bind(temperature = 0)

class GraphState(TypedDict):
    input: List[str]  # 原问题序列
    output: str  # 回答

def build_answer_recursively_graph(retrieve_callback: Callable[[str], Awaitable[List[Document]]]):
    async def answer_recursively(state: GraphState) -> str:
        questions: List[str] = state["input"]
        q_a_pairs = ""
        for q in questions:
            rag_chain = (
                    {"context": itemgetter("question") | RunnableLambda(retrieve_callback),
                     "question": itemgetter("question"),
                     "q_a_pairs": itemgetter("q_a_pairs")}
                    | decomposition_prompt
                    | llm
                    | StrOutputParser())

            answer = await rag_chain.ainvoke({"question": q, "q_a_pairs": q_a_pairs})
            q_a_pair = format_qa_pair(q, answer)
            q_a_pairs = q_a_pairs + "\n---\n" + q_a_pair

        return {"output": q_a_pairs}

    workflow = StateGraph(GraphState)

    workflow.add_node("answer_recursively_node", answer_recursively)

    workflow.add_edge(START, "answer_recursively_node")
    workflow.add_edge("answer_recursively_node", END)

    answer_recursively_graph = workflow.compile()

    return answer_recursively_graph