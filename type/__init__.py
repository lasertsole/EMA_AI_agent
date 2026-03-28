from enum import Enum

from pydantic import BaseModel
from typing import List, Optional, TypedDict

# 多模态消息体
class MultiModalMessage(BaseModel):
    text: str
    image_base64_list: Optional[List[str]] = None

class FileType(Enum):
    AUDIO = "audio"
    IMAGE = "image"

class Chat(BaseModel):
    role: str
    content: str
    timestamp: str
    audio_path_list: Optional[List[str]] =  None
    image_path_list: Optional[List[str]] =  None

class File(TypedDict):
    content: bytes
    type: FileType
    extension: str # 后缀