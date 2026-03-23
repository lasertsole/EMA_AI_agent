"""RAG tool facade (delegates to unified retrieval)."""

from __future__ import annotations
from pydantic import BaseModel, Field
from langchain_core.tools import tool, StructuredTool
from tasks.unified_retrieval import search_unified

class SearchKnowledgeSchema(BaseModel):
    query: str = Field(description="Detail question")


def _search_knowledge_tool(query: str) -> str:
    return search_unified(query)

search_knowledge_tool = StructuredTool.from_function(func=_search_knowledge_tool,  description="Hybrid retrieval over local knowledge base.")
search_knowledge_tool.handle_tool_error = True