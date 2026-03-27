from pydantic import BaseModel
from typing import List, Optional

# 多模态消息体
class MultiModalMessage(BaseModel):
    text: str
    image_base64_list: Optional[List[str]] = None
