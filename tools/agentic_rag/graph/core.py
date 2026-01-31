import os
import asyncio
from pydantic import BaseModel, Field
import pandas as pd
from typing import List
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.tools import tool
from graphrag.config.models.vector_store_schema_config import VectorStoreSchemaConfig
from graphrag.query.context_builder.entity_extraction import EntityVectorStoreKey
from graphrag.query.indexer_adapters import (
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_reports,
    read_indexer_text_units,
    read_indexer_communities,
)
from graphrag.query.question_gen.local_gen import LocalQuestionGen
from graphrag.query.structured_search.local_search.mixed_context import (
    LocalSearchMixedContext,
)
from graphrag.query.structured_search.global_search.community_context import (
    GlobalCommunityContext,
)
from graphrag.query.structured_search.drift_search.drift_context import (
    DRIFTSearchContextBuilder,
)
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.query.structured_search.global_search.search import GlobalSearch
from graphrag.query.structured_search.drift_search.search import DRIFTSearch
from graphrag.vector_stores.lancedb import LanceDBVectorStore
from graphrag.config.enums import ModelType
from graphrag.config.models.language_model_config import LanguageModelConfig
from graphrag.config.models.drift_search_config import DRIFTSearchConfig
from graphrag.language_model.manager import ModelManager
from graphrag.tokenizer.get_tokenizer import get_tokenizer

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
env_path = current_dir / '../../../.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
text_api_key = os.getenv("CHAT_API_KEY")
text_api_base = os.getenv("CHAT_API_BASE")
text_api_name = os.getenv("CHAT_API_NAME")

embedding_api_key = os.getenv("EMBEDDING_API_KEY")
embedding_api_base = os.getenv("EMBEDDING_API_BASE")
embedding_api_name = os.getenv("EMBEDDING_API_NAME")

INPUT_DIR = current_dir / "output"
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

relationship_df = pd.read_parquet(f"{INPUT_DIR}/{RELATIONSHIP_TABLE}.parquet")
relationships = read_indexer_relationships(relationship_df)

report_df = pd.read_parquet(f"{INPUT_DIR}/{COMMUNITY_REPORT_TABLE}.parquet")
reports = read_indexer_reports(report_df, community_df, COMMUNITY_LEVEL)

communities = read_indexer_communities(community_df, report_df)

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

description_embedding_store = LanceDBVectorStore(
    vector_store_schema_config=VectorStoreSchemaConfig(
        index_name="default-entity-description"
    )
)
description_embedding_store.connect(db_uri=LANCEDB_URI)

local_context_builder = LocalSearchMixedContext(
    community_reports=reports,
    text_units=text_units,
    entities=entities,
    relationships=relationships,
    entity_text_embeddings=description_embedding_store,
    embedding_vectorstore_key=EntityVectorStoreKey.ID,  # if the vectorstore uses entity title as ids, set this to EntityVectorStoreKey.TITLE
    text_embedder=text_embedder,
    tokenizer=tokenizer,
)

global_context_builder_params = {
    "use_community_summary": False,  # False means using full community reports. True means using community short summaries.
    "shuffle_data": True,
    "include_community_rank": True,
    "min_community_rank": 0,
    "community_rank_name": "rank",
    "include_community_weight": True,
    "community_weight_name": "occurrence weight",
    "normalize_community_weight": True,
    "max_tokens": 12_000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 5000)
    "context_name": "Reports",
}

global_context_builder = GlobalCommunityContext(
    community_reports=reports,
    communities=communities,
    entities=entities,  # default to None if you don't want to use community weights for ranking
    tokenizer=tokenizer,
)

local_context_builder_params = {
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

local_model_params = {
    "max_tokens": 2_000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 1000=1500)
    "temperature": 0.0,
}

map_llm_params = {
    "max_tokens": 1000,
    "temperature": 0.0,
    "response_format": {"type": "json_object"},
}

reduce_llm_params = {
    "max_tokens": 2000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 1000-1500)
    "temperature": 0.0,
}

drift_params = DRIFTSearchConfig(
    temperature=0,
    max_tokens=12_000,
    primer_folds=1,
    drift_k_followups=3,
    n_depth=3,
    n=1,
)

drift_context_builder = DRIFTSearchContextBuilder(
    model=chat_model,
    text_embedder=text_embedder,
    entities=entities,
    relationships=relationships,
    reports=reports,
    entity_text_embeddings=description_embedding_store,
    text_units=text_units,
    tokenizer=tokenizer,
    config=drift_params,
)

local_search_engine = LocalSearch(
    model=chat_model,
    context_builder=local_context_builder,
    tokenizer=tokenizer,
    model_params=local_model_params,
    context_builder_params=local_context_builder_params,
    response_type="multiple paragraphs",  # free form text describing the response type and format, can be anything, e.g. prioritized list, single paragraph, multiple paragraphs, multiple-page report
)

global_search_engine = GlobalSearch(
    model=chat_model,
    context_builder=global_context_builder,
    tokenizer=tokenizer,
    max_data_tokens=12_000,  # change this based on the token limit you have on your model (if you are using a model with 8k limit, a good setting could be 5000)
    map_llm_params=map_llm_params,
    reduce_llm_params=reduce_llm_params,
    allow_general_knowledge=False,  # set this to True will add instruction to encourage the LLM to incorporate general knowledge in the response, which may increase hallucinations, but could be useful in some use cases.
    json_mode=True,  # set this to False if your LLM model does not support JSON mode.
    context_builder_params=global_context_builder_params,
    concurrent_coroutines=32,
    response_type="multiple paragraphs",  # free form text describing the response type and format, can be anything, e.g. prioritized list, single paragraph, multiple paragraphs, multiple-page report
)

drift_search_engine = DRIFTSearch(
    model=chat_model, context_builder=drift_context_builder, tokenizer=tokenizer
)

question_generator = LocalQuestionGen(
    model=chat_model,
    context_builder=local_context_builder,
    tokenizer=tokenizer,
    model_params=local_model_params,
    context_builder_params=local_context_builder_params,
)

async def query_candidate_questions(queries:List[str])->List[str]:
    question_history = queries
    candidate_questions = await question_generator.agenerate(
        question_history=question_history, context_data=None, question_count=5
    )
    return candidate_questions.response

# 工具输入参数
class BackgroundInfoQuerySchema(BaseModel):
    query: str = Field(description="具体问题")

@tool(args_schema=BackgroundInfoQuerySchema, description="""
       检索“魔法少女的魔女审批”相关知识的工具函数。

       该函数用于当需要回答与“魔法少女的魔女审批”相关的问题时调用，
       通过本地检索引擎获取知识库中的对应答案。

       Args:
           query (str): 具体的查询问题，需与“魔法少女的魔女审批”主题相关。

       Returns:
           str: 本地检索引擎从知识库中检索到的答案文本。
   """)
async def query_background_info(query:str)-> str:
    result = await local_search_engine.search(query)
    return result.response

#async def test():
#    result = await drift_search_engine.search("艾玛生日什么时候?")
#    print(result.response)


#asyncio.run(test())