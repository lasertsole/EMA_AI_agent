import json
import time
from enum import Enum
from pathlib import Path
from collections import deque
from pydantic import BaseModel
from typing import List, Optional, TypedDict, Deque

current_dir = Path(__file__).parent.resolve()
SESSION_FOLDER = current_dir / '../src/session'
SESSION_FOLDER = SESSION_FOLDER.resolve()

CHATS_STORAGE_FILE = SESSION_FOLDER / "chats_storage.jsonl"
CHATS_STORAGE_FILE = CHATS_STORAGE_FILE.resolve()

class FileType(Enum):
    AUDIO = "audio"
    IMAGE = "image"

class Chat(BaseModel):
    role: str
    content: str
    audio_path_list: Optional[List[str]] =  None
    image_path_list: Optional[List[str]] =  None
    timestamp: float = time.time_ns()

class File(TypedDict):
    content: bytes
    type: FileType

# 聊天记录存储类
class ChatStorage:
    _chats_deque: deque[Chat]

    def __init__(self, chats_maxlen: int = 20):
        # 获取已持久化的聊天记录
        chats_list: List[Chat] = []

        SESSION_FOLDER.mkdir(parents=True, exist_ok=True)
        with open(CHATS_STORAGE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                chats_list.append(Chat(**json.loads(line.strip())))

        # 根据时间戳排序聊天记录,从新到旧
        chats_list.sort(key=lambda x: x.timestamp)

        # 将新聊天记录装入双向列表
        self._chats_deque = deque(chats_list[-chats_maxlen:], maxlen=chats_maxlen)

        # 将旧聊天记录装入旧聊天记录列表
        old_chats_list = chats_list[:-chats_maxlen]

        # 将聊天记录对应的文件删除
        self.delete_file_from_chats(old_chats_list)

        # 将新聊天记录列表写回文件
        self.storage_chats_deque(self._chats_deque)

    def get_chats(self) -> List[Chat]:
        return list(self._chats_deque)

    def delete_file_from_chats(self, chats_list: List[Chat]):
        # 将聊天记录对应的文件删除
        for chat in chats_list:
            for file_path in chat.audio_path_list:
                try:
                    if Path(file_path).exists():
                        Path(file_path).unlink()
                except Exception as e:
                    pass
            for file_path in chat.image_path_list:
                try:
                    if Path(file_path).exists():
                        Path(file_path).unlink()
                except Exception as e:
                    pass

    def storage_chats_deque(self, _chats_deque: Deque[Chat]):
        SESSION_FOLDER.mkdir(parents=True, exist_ok=True)

        # 将新聊天记录列表写回文件
        with open(CHATS_STORAGE_FILE, 'w', encoding='utf-8') as f:
            for chat in _chats_deque:
                f.write(json.dumps(chat.model_dump(), ensure_ascii=False) + "\n")

    def add_chat(self, new_chat: Chat, files: Optional[List[File]] = None):
        # 将新聊天记录装入双向列表
        self._chats_deque.append(new_chat)

        # 将文件写入文件夹
        file_path_list = []
        audio_path_list = []
        image_path_list = []
        if files:
            for file in files:
                folder_path = SESSION_FOLDER / file["type"].value
                file_path = folder_path / str(time.time_ns())
                file_path = file_path.as_posix()

                match file["type"]:
                    case FileType.AUDIO:
                        file_path = file_path + '.wav'
                        audio_path_list.append(file_path)
                    case FileType.IMAGE:
                        file_path = file_path + '.jpg'
                        image_path_list.append(file_path)
                    case _:
                        raise ValueError("Invalid file type")

                # 确保目录存在
                Path(folder_path).mkdir(parents=True, exist_ok=True)

                with open(file_path, "wb") as f:
                    f.write(file["content"])
                    file_path_list.append(file_path)

        # 将文件路径写入新聊天记录
        new_chat.audio_path_list = audio_path_list
        new_chat.image_path_list = image_path_list

        # 将聊天记录追加到文件末尾
        with open(CHATS_STORAGE_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(new_chat.model_dump(), ensure_ascii=False) + "\n")