import os
import datetime
import operator
from dotenv import load_dotenv
from langchain_core.retrievers import BaseRetriever
from langgraph.types import Send
from pydantic import BaseModel, Field
from typing import List, Annotated, Callable, TypedDict
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from .mutil_query import mutil_query_graph
from .rag_fusion import rag_fusion_graph

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../.env')
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

query_transform_Template = """
你是一名人工智能语言模型助手。
你的任务是针对用户提出的原问题，生成多个不同的表述版本(少于等于五个)，用于从向量数据库中检索相关文档。
通过为用户的问题生成多种切入视角，助力用户突破基于距离的相似度检索的部分局限性。
请将这些不同的提问版本用换行符分隔呈现,并且如果用户的查询是疑问句时，请重写为陈述句。
辅助信息:当前时间为{dataTime} 原问题：{question}"""
query_transform_Template = PromptTemplate(
    template=query_transform_Template,
    input_variables=["query", "dataTime"]
)
query_transformations_Template = query_transform_Template.partial(
    dataTime=datetime.datetime.now().strftime("%Y年%m月%d日"))

chat_model = init_chat_model(
    model_provider=model_provider,
    model=api_name,
    api_key=api_key,
    temperature=0,
    max_retries=2
)


class QueryTransformationOutput(BaseModel):
    """字符串列表输出结构"""
    query_transformations: List[str] = Field(
        description="生成的重写后的多个句子。",
        examples=[[
            "西瓜每斤的价格。",
            "当前西瓜市场零售价格。",
            "不同品种（如麒麟瓜、黑美人等）西瓜的产地批发价与市场零售价差异。",
            "影响西瓜价格的主要因素（季节、产地、运输成本等）。",
            "如何根据市场行情判断西瓜的合理购买价格。"
        ]]
    )


query_transformations = query_transformations_Template | chat_model.with_structured_output(QueryTransformationOutput)


class GraphState(TypedDict):
    input: str  # 原问题
    query_transformations: List[str]  # 变换后的问题列表
    answers: Annotated[List[List[str]], operator.add]
    output: str  # 查询结果


class JudgeState(TypedDict):
    query_transformation: str  # 单个变换后的问题


async def query_transform_node(state: GraphState):
    result: QueryTransformationOutput = await query_transformations.ainvoke(state["input"])
    return {"query_transformations": result.query_transformations}


def mapper(state: GraphState) -> List[Send]:
    return [Send("query_judge_node", {"query_transformation": query_transformation}) for query_transformation in
            state["query_transformations"]]

def build_query_by_re_writen_graph(retriever: BaseRetriever):
    async def query_judge_node(state: JudgeState):
        documents = retriever.invoke(state["query_transformation"], k=10, score_threshold=0.5)
        retrieveResults = [doc.page_content for doc in documents]
        return {"answers": [retrieveResults]}

    def query_fusion_node(state: GraphState):
        k=60
        fused_scores = {}

        for retrieve_list in state["answers"]:
            for rank, text in enumerate(retrieve_list):
                if text not in fused_scores:
                    fused_scores[text] = 0
                fused_scores[text] += 1 / (rank + k)
        res = [
            text
            for text, _ in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        ]

        return { 'output': res }

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