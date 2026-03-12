from .web_search import web_search_tool
from .fetch_url import build_fetch_tool
from .python_repl import build_python_repl_tool
from .rag import search_knowledge_tool
from .read_file import build_read_file_tool
from .terminal import build_terminal_tool

# 核心工具
CORE_TOOLS = [
    build_python_repl_tool(),
    build_read_file_tool()
]

# 全部工具
ALL_TOOLS = [
    *CORE_TOOLS,
    search_knowledge_tool,
    web_search_tool,
    build_terminal_tool(),
    build_fetch_tool(),
]