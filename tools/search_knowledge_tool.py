"""SearchKnowledgeBaseTool - LlamaIndex hybrid search (BM25 + Vector)."""
from pathlib import Path
from models import embed_model
from typing import Type, Optional
from pydantic import BaseModel, Field


class SearchKnowledgeInput(BaseModel):
    query: str = Field(description="The search query to find relevant knowledge")

class SearchKnowledgeBaseTool(BaseModel):
    name:str = "search_knowledge_base"
    description: str = (
        "Search the local knowledge base using hybrid retrieval (keyword + semantic)."
        "Use this when the user asks about specific knowledge or documents."
        "Returns the most relevant passages from the knowledge base."
    )
    args_schema: Type[BaseModel] = SearchKnowledgeInput
    base_dir: str = ""
    _index: Optional[object] = None

    class Config:
        arbitrary_types_allowed = True

    def _build_index(self):
        """Build or load LlamaIndex index from knowledge/ directory."""
        knowledge_dir = Path(self.base_dir) / "knowledge"
        storage_dir = Path(self.base_dir) / "storage"

        if not knowledge_dir.exists() or not any(knowledge_dir.iterdir()):
            raise None

        try:
            from llama_index.core import (
                SimpleDirectoryReader,
                StorageContext,
                VectorStoreIndex,
                load_index_from_storage
            )
            from llama_index.core.settings import Settings
            from llama_index.embeddings.openai import OpenAIEmbedding

            Settings.embed_model = embed_model

            if storage_dir.exists() and any(storage_dir.iterdir()):
                try:
                    storage_context = StorageContext.from_defaults(
                        persist_dir=str(storage_dir)
                    )
                    return load_index_from_storage(storage_context)
                except Exception:
                    pass

                # Build fresh index
                documents = SimpleDirectoryReader(
                    str(knowledge_dir), recursive=True
                ).load_data()

                if not documents:
                    return None

                index = VectorStoreIndex.from_documents(documents)
                storage_dir.mkdir(parents=True, exist_ok=True)
                index.storage_context.persist(persist_dir=str(storage_dir))
                return index
        except ImportError as e:
            raise ImportError(f"LlamaIndex not fully installed: {e}")
        except Exception as e:
            raise Exception(f"Index build error: {e}")

    def _run(self, query: str)-> str:
        if self._index is None:
            self._index = self._build_index()

        if self._index is None:
            return "Knowledge base is empty. Add documents to backend/knowledge/ to enable retrieve."

        try:
            query_engine = self._index.as_query_engine(similarity_top_k=3)
            response = query_engine.query(query)
            result = str(response)
            if len(result) > 5000:
                result = result[:5000] + "\n...[truncated]"
            return result
        except Exception as e:
            return f"Search error: {str(e)}"

def create_search_knowledge_base_tool(base_dir: Path) -> SearchKnowledgeBaseTool:
    return SearchKnowledgeBaseTool(base_dir=str(base_dir))