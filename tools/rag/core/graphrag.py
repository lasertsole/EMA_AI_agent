import os
import pandas as pd
import tiktoken
from graphrag.query.context_builder.entity_extraction import EntityVectorStoreKey
from graphrag.query.indexer_adapters import (
    read_indexer_covariates,
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_reports,
    read_indexer_text_units,
)
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.vector_stores.lancedb import LanceDBVectorStore

INPUT_DIR = './graphrag_source/output'
LANCEDB_URI = f"{INPUT_DIR}/lancedb"

COMMUNITY_REPORT_TABLE = "community_reports"
ENTITY_TABLE = "entities"
ENTITY_EMBEDDING_TABLE = ""
RELATIONSHIP_TABLE = "relationships"
TEXT_UNIT_TABLE = "text_units"
COMMUNITY_LEVEL = 2