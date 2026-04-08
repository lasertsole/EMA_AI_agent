from typing import List

from langchain_core.tools import BaseTool

from tools import web_search_tool
from .text_rag_tool import text_rag_tool

# 全部工具
ALL_TOOLS: List[BaseTool] = [
    web_search_tool,
    text_rag_tool
]

__all__ = [
    "ALL_TOOLS"
]