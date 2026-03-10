from .web_search import web_search
from .fetch_url import build_fetch_tool
from .python_repl import build_python_repl_tool
from .rag import search_knowledge_base
from .read_file import build_read_file_tool
from .terminal import build_terminal_tool
from langchain_core.tools import Tool

# 核心工具
CORE_TOOLS = [
    build_python_repl_tool(),
    build_read_file_tool()
]

# 全部工具
ALL_TOOLS = [
    *CORE_TOOLS,
    web_search,
    build_terminal_tool(),
    build_fetch_tool(),
    Tool.from_function(
        name="search_knowledge_base",
        description="Hybrid retrieval over local knowledge base.",
        func=search_knowledge_base,
    ),
]