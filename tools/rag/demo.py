import chromadb
from langchain_chroma import Chroma
from pathlib import Path
from dataclasses import dataclass, field, asdict
from collections import defaultdict, Counter
from typing import Optional

CHROMA_PERSIST_DIR = './chroma_db_persist_dir'
COLLECTION_NAME = 'knowledge_graph'

OUTPUT_DIR = Path("./output")
OUTPUT_DIR.mkdir(exist_ok = True)

@dataclass
class KnowledgeExtraction:
    """知识提取结果（带溯源）"""
    doc_id: str                                     # 文档 ID
    doc_title: str                                  # 文档标题
    extraction_class: str                           # 提取类型（实体、关系、事件等）
    extraction_text: str                            # 提取的原文文本
    char_interval: Optional[dict] = None            # 原文字符区间（溯源的核心）
    attributes: dict = field(default_factory=dict)  # 属性信息

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return asdict(self)

    def to_searchable_text(self):
        parts = [
            f"类型: {self.extraction_class}",
            f"内容: {self.extraction_text}",
            f"来源: {self.doc_title}"
        ]
        if self.attributes:
            for k, v in self.attributes.items():
                parts.append(f"{k}: {v}")
        return " | ".join(parts)