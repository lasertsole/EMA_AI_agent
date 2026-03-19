import asyncio

from langchain_core.messages import HumanMessage

from agent import agent

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableLambda

from tools import ALL_TOOLS
from models import base_model
from langchain.agents import create_agent
from middlewares import dynamic_model_routing, tool_calling_limit

def route_model(input_data):
    print(input_data)
    return base_model.bind_tools(ALL_TOOLS)

dynamic_llm = RunnableLambda(route_model)


#生成agent对象
agent = create_agent(
    model = dynamic_llm,
    middleware=[tool_calling_limit],
)

async def main():
    result = await agent.ainvoke({"messages": [HumanMessage(content="帮我查查 mate80pro什么时候发售")]})
    print(result)

if __name__ == "__main__":
    asyncio.run(main())