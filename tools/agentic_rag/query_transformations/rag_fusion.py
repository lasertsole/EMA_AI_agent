from typing import List
from langgraph.graph import StateGraph, START, END, MessagesState

class GraphState(MessagesState):
    input: List[List[str]] # 查询结果列表 的 列表
    output: List[str]  # 查询结果列表


def rag_fusion_node(state: GraphState):
    k = 60
    fused_scores = {}

    for retrieve_list in state["input"]:
        for rank, text in enumerate(retrieve_list):
            if text not in fused_scores:
                fused_scores[text] = 0
            fused_scores[text] += 1 / (rank + k)

    res = [
        text
        for text, _ in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    ]

    return {'output': res }


workflow = StateGraph(GraphState)

workflow.add_node("rag_fusion_node", rag_fusion_node)

workflow.add_edge(START, "rag_fusion_node")
workflow.add_edge("rag_fusion_node", END)

rag_fusion_graph = workflow.compile()