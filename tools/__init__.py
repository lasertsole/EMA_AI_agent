from .agentic_rag import *
from typing import List, Any

from .web_search import web_search
from .fetch_url_tool import create_fetch_url_tool
from .python_repl_tool import create_python_repl_tool
from .read_file_tool import create_read_file_tool
from .terminal_tool import create_terminal_tool
from .search_knowledge_tool import create_search_knowledge_base_tool

def get_all_tools(root_dir: str)-> List[Any]:
    fetch_url_tool = create_fetch_url_tool()
    python_repl_tool = create_python_repl_tool()
    read_file_tool = create_read_file_tool(root_dir)
    terminal_tool = create_terminal_tool(root_dir)
    search_knowledge_tool = create_search_knowledge_base_tool(root_dir)

    return [
        fetch_url_tool,
        python_repl_tool,
        read_file_tool,
        terminal_tool,
        search_knowledge_tool
    ]