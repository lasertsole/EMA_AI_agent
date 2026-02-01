import os
import operator
from dotenv import load_dotenv
from langgraph.types import Send
from .rag_fusion import rag_fusion_graph
from langchain_core.documents import Document
from langgraph.graph import StateGraph, START, END
from typing import List, Annotated, TypedDict, Callable, Awaitable
from .mutil_query import mutil_query_graph, QueryTransformationOutput

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../.env')
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

class GraphState(TypedDict):
    input: str  # 原问题
    query_transformations: List[str]  # 变换后的问题列表
    answers: Annotated[List[List[Document]], operator.add]
    output: str  # 查询结果


class JudgeState(TypedDict):
    query_transformation: str  # 单个变换后的问题


async def query_transform_node(state: GraphState):
    result: QueryTransformationOutput = await mutil_query_graph.ainvoke({"input" : state["input"]})
    return {"query_transformations": result["output"]}

def mapper(state: GraphState) -> List[Send]:
    return [Send("query_judge_node", {"query_transformation": query_transformation}) for query_transformation in
            state["query_transformations"]]

def build_query_by_re_writen_graph(retrieve_callback: Callable[[str], Awaitable[List[Document]]]):
    async def query_judge_node(state: JudgeState):
        documents:List[Document] = await retrieve_callback(state["query_transformation"])
        return { "answers" : [documents]}

    async def query_fusion_node(state: GraphState):
        res = await rag_fusion_graph.ainvoke({"input": state["answers"]})
        return { 'output': res["output"] }

    workflow = StateGraph(GraphState)

    workflow.add_node("query_transform_node", query_transform_node)
    workflow.add_node("query_judge_node", query_judge_node)
    workflow.add_node("query_fusion_node", query_fusion_node)

    workflow.add_edge(START, "query_transform_node")
    workflow.add_conditional_edges("query_transform_node", mapper, ["query_judge_node"])
    workflow.add_edge("query_judge_node", "query_fusion_node")
    workflow.add_edge("query_fusion_node", END)

    graph = workflow.compile()
    return graph