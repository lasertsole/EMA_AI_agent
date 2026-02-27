import json
import time
from enum import Enum
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional, TypedDict

current_dir = Path(__file__).parent.resolve()
SESSION_FOLDER = current_dir / '../src/session'
SESSION_FOLDER = SESSION_FOLDER.resolve()

CHATS_STORAGE_FILE = SESSION_FOLDER / "chats_storage.jsonl"
CHATS_STORAGE_FILE = CHATS_STORAGE_FILE.resolve()

class FileType(Enum):
    AUDIO = "audio"
    IMAGE = "image"

class Chat(BaseModel):
    sender: str
    content: str
    audios_name: Optional[List[str]] =  None
    images_name: Optional[List[str]] =  None
    timestamp: float = time.time()

def add_chats(chats: List[Chat]):
    # 确保目录存在
    SESSION_FOLDER.mkdir(parents=True, exist_ok=True)

    with open(CHATS_STORAGE_FILE, 'w', encoding='utf-8') as f:
        for chat in chats:
            f.write(json.dumps(chat, ensure_ascii=False) + "\n")

def get_chats() -> List[Chat]:
    # 确保目录存在
    SESSION_FOLDER.mkdir(parents=True, exist_ok=True)
    res = []
    with open(CHATS_STORAGE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            res.append(json.loads(line.strip()))
    return res

class File(TypedDict):
    content: bytes
    type: FileType

def add_files(files: List[File])-> List[str]:
    file_path_list = []
    for file in files:
        folder_path= SESSION_FOLDER / file["type"].value
        file_path = folder_path / str(time.time_ns())
        file_path = file_path.as_posix()

        match file["type"]:
            case FileType.AUDIO:
                file_path = file_path + '.wav'
            case FileType.IMAGE:
                file_path = file_path + '.jpg'
            case _:
                raise ValueError("Invalid file type")

        # 确保目录存在
        Path(folder_path).mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(file["content"])
            file_path_list.append(file_path)

    return file_path_list
