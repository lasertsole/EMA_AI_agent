from typing import List, Optional
from pydantic import BaseModel

# 多模态消息体
class MultiModalMessage(BaseModel):
    text: str
    image_base64_list: Optional[List[str]] = None