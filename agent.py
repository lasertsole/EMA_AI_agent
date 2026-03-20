from enum import Enum
from tools import ALL_TOOLS
from langchain.agents import create_agent
from middlewares import tool_calling_limit
from langgraph.graph.state import CompiledStateGraph
from models import chat_model, reasoner_model, vl_model

class ModelType(Enum):
    """字符串枚举，可以直接与字符串比较"""
    CHAT_MODEL = chat_model
    REASONER_MODEL = reasoner_model
    VL_MODEL = vl_model

def built_agent(model_type:ModelType = ModelType.CHAT_MODEL, temperature: float = 0.8, enable_tool: bool = True)->CompiledStateGraph:
    model = model_type.value.bind(temperature=temperature)
    #生成agent对象
    agent = create_agent(
        model = model,
        tools=ALL_TOOLS if enable_tool else None,
        middleware=[tool_calling_limit],
    )
    return agent