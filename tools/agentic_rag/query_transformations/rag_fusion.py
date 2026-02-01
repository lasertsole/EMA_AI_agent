from typing import List
from langchain_core.documents import Document
from langgraph.graph import StateGraph, START, END, MessagesState

class GraphState(MessagesState):
    input: List[List[Document]] # 查询结果列表 的 列表
    output: List[Document]  # 查询结果列表


def rag_fusion_node(state: GraphState):
    k = 60
    fused_scores = {}
    fused_docs = {}

    for retrieve_list in state["input"]:
        for rank, doc in enumerate(retrieve_list):
            text = doc.page_content
            if text not in fused_scores:
                fused_scores[text] = 0
                fused_docs[text] = doc
            fused_scores[text] += 1 / (rank + k)

    fused_text_list = [
        text
        for text, _ in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    ]

    fused_text_doc = [fused_docs[text] for text in fused_text_list]

    return {'output': fused_text_doc }


workflow = StateGraph(GraphState)

workflow.add_node("rag_fusion_node", rag_fusion_node)

workflow.add_edge(START, "rag_fusion_node")
workflow.add_edge("rag_fusion_node", END)

rag_fusion_graph = workflow.compile()