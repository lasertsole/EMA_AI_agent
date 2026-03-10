from models import base_model
from langchain.agents import create_agent
from middlewares import dynamic_model_routing, summarization, tool_calling_limit
from tools import ALL_TOOLS

#生成agent对象
agent = create_agent(
    model = base_model,
    tools = ALL_TOOLS,
    middleware=[dynamic_model_routing, summarization, tool_calling_limit],
)