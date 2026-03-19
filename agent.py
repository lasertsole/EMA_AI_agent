from langchain.agents import create_agent
from middlewares import tool_calling_limit
from tools import ALL_TOOLS
from langchain_core.runnables import ConfigurableField
from models import chat_model, reasoner_model, vl_model

# 创建动态模型
dynamic_llm = chat_model.configurable_alternatives(
    ConfigurableField(id = "model_type"),
    default_key="chat_model",
    reasoner_model=reasoner_model,
    vl_model=vl_model
)

#生成agent对象
agent = create_agent(
    model = dynamic_llm,
    tools=ALL_TOOLS,
    middleware=[tool_calling_limit],
)