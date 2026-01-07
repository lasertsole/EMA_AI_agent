from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from models import basic_model
from middlewares import dynamic_model_routing, summarization
from tools import web_search

with open("personality.txt", "r", encoding="utf-8") as f:
    personality = f.read()

# 线程记忆功能
checkpoint = InMemorySaver()

#生成agent对象
agent = create_agent(
    model=basic_model,
    tools=[web_search],
    system_prompt=personality,
    checkpointer=checkpoint,
    middleware=[dynamic_model_routing, summarization],
)