import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from models import extract_model

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

current_dir = Path(__file__).parent.resolve()
TXT_PATH = current_dir / "rag_source/allCharacters.txt"

txt_file= Path(TXT_PATH)

# 检查文件是否存在
if txt_file.exists():
    file_size = txt_file.stat().st_size
    print(f"文件大小：({file_size/1024:.2f} KB)")

parse_start_time = time.time()

extract_model.invoke([txt_file])