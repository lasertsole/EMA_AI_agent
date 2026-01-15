import os
import asyncio
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from graphrag.config.models.vector_store_schema_config import VectorStoreSchemaConfig
from graphrag.query.context_builder.entity_extraction import EntityVectorStoreKey
from graphrag.query.indexer_adapters import (
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_reports,
    read_indexer_text_units,
)
from graphrag.query.question_gen.local_gen import LocalQuestionGen
from graphrag.query.structured_search.local_search.mixed_context import (
    LocalSearchMixedContext,
)
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.vector_stores.lancedb import LanceDBVectorStore
from graphrag.config.enums import ModelType
from graphrag.config.models.language_model_config import LanguageModelConfig
from graphrag.language_model.manager import ModelManager
from graphrag.tokenizer.get_tokenizer import get_tokenizer

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../.env')
load_dotenv(env_path, override = True)
text_api_key = os.getenv("CHAT_API_KEY")
text_api_base = os.getenv("CHAT_API_BASE")
text_api_name = os.getenv("CHAT_API_NAME")

embedding_api_key = os.getenv("EMBEDDING_API_KEY")
embedding_api_base = os.getenv("EMBEDDING_API_BASE")
embedding_api_name = os.getenv("EMBEDDING_API_NAME")

current_dir = Path(__file__).parent.resolve()
INPUT_DIR = current_dir / "graphrag_source/output"
INPUT_DIR = INPUT_DIR.as_posix()
LANCEDB_URI = f"{INPUT_DIR}/lancedb"

COMMUNITY_REPORT_TABLE = "community_reports"
ENTITY_TABLE = "entities"
COMMUNITY_TABLE = "communities"
RELATIONSHIP_TABLE = "relationships"
COVARIATE_TABLE = "covariates"
TEXT_UNIT_TABLE = "text_units"
COMMUNITY_LEVEL = 2

entity_df = pd.read_parquet(f"{INPUT_DIR}/{ENTITY_TABLE}.parquet")
community_df = pd.read_parquet(f"{INPUT_DIR}/{COMMUNITY_TABLE}.parquet")

entities = read_indexer_entities(entity_df, community_df, COMMUNITY_LEVEL)

description_embedding_store = LanceDBVectorStore(
    vector_store_schema_config=VectorStoreSchemaConfig(
        index_name="default-entity-description"
    )
)
description_embedding_store.connect(db_uri=LANCEDB_URI)

relationship_df = pd.read_parquet(f"{INPUT_DIR}/{RELATIONSHIP_TABLE}.parquet")
relationships = read_indexer_relationships(relationship_df)

report_df = pd.read_parquet(f"{INPUT_DIR}/{COMMUNITY_REPORT_TABLE}.parquet")
reports = read_indexer_reports(report_df, community_df, COMMUNITY_LEVEL)

text_unit_df = pd.read_parquet(f"{INPUT_DIR}/{TEXT_UNIT_TABLE}.parquet")
text_units = read_indexer_text_units(text_unit_df)

chat_config = LanguageModelConfig(
    api_key=text_api_key,
    type=ModelType.OpenAIChat,
    model_provider="openai",
    api_base=text_api_base,
    model=text_api_name,
    max_retries=20,
    encoding_model="cl100k_base"
)
chat_model = ModelManager().get_or_create_chat_model(
    name="local_search",
    model_type=ModelType.OpenAIChat,
    config=chat_config,
)

embedding_config = LanguageModelConfig(
    api_key=embedding_api_key,
    type=ModelType.OpenAIEmbedding,
    model_provider="openai",
    api_base=embedding_api_base,
    model=embedding_api_name,
    max_retries=20,
    encoding_model="cl100k_base",
)

text_embedder = ModelManager().get_or_create_embedding_model(
    name="local_search_embedding",
    model_type=ModelType.OpenAIEmbedding,
    config=embedding_config,
)

tokenizer = get_tokenizer(chat_config)

context_builder = LocalSearchMixedContext(
    community_reports=reports,
    text_units=text_units,
    entities=entities,
    relationships=relationships,
    entity_text_embeddings=description_embedding_store,
    embedding_vectorstore_key=EntityVectorStoreKey.ID,  # if the vectorstore uses entity title as ids, set this to EntityVectorStoreKey.TITLE
    text_embedder=text_embedder,
    tokenizer=tokenizer,
)

local_context_params = {
    "text_unit_prop": 0.5,
    "community_prop": 0.1,
    "conversation_history_max_turns": 5,
    "conversation_history_user_turns_only": True,
    "top_k_mapped_entities": 10,
    "top_k_relationships": 10,
    "include_entity_rank": True,
    "include_relationship_weight": True,
    "include_community_rank": False,
    "return_candidate_context": False,
    "embedding_vectorstore_key": EntityVectorStoreKey.ID,  # set this to EntityVectorStoreKey.TITLE if the vectorstore uses entity title as ids
    "max_tokens": 12_000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 5000)
}

model_params = {
    "max_tokens": 2_000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 1000=1500)
    "temperature": 0.0,
}

search_engine = LocalSearch(
    model=chat_model,
    context_builder=context_builder,
    tokenizer=tokenizer,
    model_params=model_params,
    context_builder_params=local_context_params,
    response_type="multiple paragraphs",  # free form text describing the response type and format, can be anything, e.g. prioritized list, single paragraph, multiple paragraphs, multiple-page report
)

async def text():
    result = await search_engine.search("艾玛的生日是什么时候?")
    print(result.response)

asyncio.run(text())