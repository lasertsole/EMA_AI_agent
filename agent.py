from typing import Any
from models import base_model
from langchain_core.tools import Tool
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from workspace.prompt_builder import build_system_prompt
from middlewares import dynamic_model_routing, summarization, tool_calling_limit
from tools import web_search, build_terminal_tool, build_python_repl_tool, build_fetch_tool, build_read_file_tool, search_knowledge_base

# 线程记忆功能
checkpoint = InMemorySaver()

def _build_tools() -> list[Any]:
    return [
        web_search,
        build_terminal_tool(),
        build_python_repl_tool(),
        build_fetch_tool(),
        build_read_file_tool(),
        Tool.from_function(
            name="search_knowledge_base",
            description="Hybrid retrieval over local knowledge base.",
            func=search_knowledge_base,
        ),
    ]

#生成agent对象
agent = create_agent(
    model=base_model,
    tools=_build_tools(),
    system_prompt = build_system_prompt(),
    checkpointer=checkpoint,
    middleware=[dynamic_model_routing, summarization, tool_calling_limit],
)