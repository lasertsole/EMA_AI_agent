from models import reasoner_model
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent

# 线程记忆功能
checkpoint = InMemorySaver()

researcher_systemPrompt = """
你是资深检索策略专家。你的目标是分析用户的问题，并调用检索工具获取准确的事实信息。
你不需要利用自身知识库回答问题，所有信息必须来源于外部工具。
"""
#生成agent对象
researcher_agent = create_agent(
    model=reasoner_model,
    system_prompt = researcher_systemPrompt,
    checkpointer=checkpoint,
)

rewrite_systemPrompt = """
"""
rewrite_agent = create_agent(
    model=reasoner_model,
    system_prompt=rewrite_systemPrompt,
    checkpointer=checkpoint,
)