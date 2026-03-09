from typing import Any
from models import base_model
from langchain_core.tools import Tool
from langchain.agents import create_agent
from middlewares import dynamic_model_routing, summarization, tool_calling_limit
from tools import web_search, build_terminal_tool, build_python_repl_tool, build_fetch_tool, build_read_file_tool, search_knowledge_base


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
    middleware=[dynamic_model_routing, summarization, tool_calling_limit],
)