import asyncio
from models import base_model, reasoner_model
from langchain_core.prompts import PromptTemplate
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent
from pydantic import BaseModel, Field
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END

# 线程记忆功能
checkpoint = InMemorySaver()

researcher_systemPrompt = """
你是资深检索策略专家。你的目标是分析用户的问题，并调用检索工具获取准确的事实信息。
你不需要利用自身知识库回答问题，所有信息必须来源于外部工具。
"""
#生成agent对象
researcher = create_agent(
    model=reasoner_model,
    system_prompt = researcher_systemPrompt
)

rewriter_systemPrompt = """
您作为专业信息优化助手，需重写用户查询使其更精确且便于检索。
查询:{query}
重写后的查询:
"""

rewriter_systemPrompt_Template = PromptTemplate(
    template=rewriter_systemPrompt,
    input_variables=["query"]
)

class ReWriteQueryListOutput(BaseModel):
    """字符串列表输出结构"""
    reQueries: list[str] = Field(
        description="生成的重写后的查询列表",
        examples=[[
            "当前西瓜市场零售价格是多少钱一斤？",
            "不同品种（如麒麟瓜、黑美人等）西瓜的产地批发价与市场零售价差异？",
            "影响西瓜价格的主要因素（季节、产地、运输成本等）有哪些？",
            "如何根据市场行情判断西瓜的合理购买价格？"]]
    )

rewriter = rewriter_systemPrompt_Template | base_model.with_structured_output(ReWriteQueryListOutput)



class GraphState(TypedDict):
    query: str # 原问题
    reQueries: list[str] # 重写后问题列表
    res: str # 查询结果

async def rewriter_node(state: GraphState):
    result = await rewriter.ainvoke({"query": "西瓜多少元一斤?"})
    print(result.reQueries)
    print(state["query"])
    return {"query": result.reQueries[0], "reQueries": result.reQueries}

async def researcher_node(state: GraphState):
    print(state["reQueries"])
    return {"res": "123"}

workflow = StateGraph(GraphState)
workflow.add_node("rewriter", rewriter_node)
workflow.add_node("researcher", researcher_node)
workflow.add_edge(START, "rewriter")
workflow.add_edge("rewriter", "researcher")
workflow.add_edge("researcher", END)
graph = workflow.compile()


# 运行异步主函数
if __name__ == "__main__":
    async def test():
        result = await rewriter.ainvoke({"query": "西瓜多少元一斤?"})
        print(result.reQueries)

    async def test1():
        result = await graph.ainvoke({"query": "西瓜多少元一斤?"})
        print(result)
    asyncio.run(test1())
