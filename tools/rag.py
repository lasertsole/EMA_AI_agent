"""RAG tool facade (delegates to unified retrieval)."""

from __future__ import annotations
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from tasks.unified_retrieval import search_unified

class SearchKnowledgeSchema(BaseModel):
        query: str = Field(description="Detail questi")

@tool(args_schema=SearchKnowledgeSchema, description="""Hybrid retrieval over local knowledge base.""")
def search_knowledge_tool(query: str) -> str:
    return search_unified(query)
