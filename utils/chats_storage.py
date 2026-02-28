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
    timestamp: float = time.time()

class File(TypedDict):
    content: bytes
    type: FileType

# 聊天记录存储类
class ChatStorage:
    chats_maxlen: int = 20
    chats_deque: deque[Chat]

    def __init__(self, chats_maxlen: int = 20):
        self.chats_maxlen = chats_maxlen
        self.chats_deque = deque(maxlen=self.chats_maxlen)

    def delete_file_from_chats(self, chats_list: List[Chat]):
        # 将聊天记录对应的文件删除
        for chat in chats_list:
            for file_name in chat.audios_name:
                Path(file_name).unlink()
            for file_name in chat.images_name:
                Path(file_name).unlink()

    def storage_chats_deque(self, chats_deque: Deque[Chat]):
        SESSION_FOLDER.mkdir(parents=True, exist_ok=True)

        # 将新聊天记录列表写回文件
        with open(CHATS_STORAGE_FILE, 'w', encoding='utf-8') as f:
            for chat in chats_deque:
                f.write(json.dumps(chat, ensure_ascii=False) + "\n")


    def get_new_chats_and_delete_old_chats(self) -> List[Chat]:
        SESSION_FOLDER.mkdir(parents=True, exist_ok=True)

        # 获取已持久化的聊天记录
        chats_list: List[Chat] = []
        with open(CHATS_STORAGE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                chats_list.append(json.loads(line.strip()))

        # 根据时间戳排序聊天记录,从新到旧
        chats_list.sort(key=lambda x: x.timestamp)

        # 将新聊天记录装入双向列表
        self.chats_deque = deque(chats_list[-self.chats_maxlen:], maxlen=self.chats_maxlen)

        # 将旧聊天记录装入旧聊天记录列表
        old_chats_list = chats_list[self.chats_maxlen:]

        # 将聊天记录对应的文件删除
        self.delete_file_from_chats(old_chats_list)

        # 将新聊天记录列表写回文件
        self.storage_chats_deque(self.chats_deque)

        return list(self.chats_deque)

    def add_chat(self, new_chat: Chat, files: List[File]):
        # 获取最旧的聊天信息
        old_chat = self.chats_deque[0]

        # 将聊天记录对应的文件删除
        self.delete_file_from_chats([old_chat])

        # 将新聊天记录装入双向列表
        self.chats_deque.append(new_chat)

        # 将文件写入文件夹
        file_path_list = []
        audio_path_list = []
        image_path_list = []
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
            f.write(json.dumps(new_chat, ensure_ascii=False) + "\n")