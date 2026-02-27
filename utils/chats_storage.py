import sqlite3
import os
import time
from enum import Enum
from typing import List, Optional, Union
class FileType(Enum):
    AUDIOS = "audios"
    IMAGES = "images"

# --- 配置 ---
FILE_FOLDER = '../src/file_folder'
os.makedirs(FILE_FOLDER, exist_ok=True)  # 确保上传文件夹存在


# --- 数据库初始化 ---
def init_storage():
    conn = sqlite3.connect('../src/db/chat_history.db')
    conn.execute("PRAGMA foreign_keys = ON;")  # 关键：开启外键支持
    cursor = conn.cursor()

    # 创建表的SQL语句
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL CHECK(sender IN ('user', 'assistant')),
            content TEXT,
            audios_path TEXT,
            images_path TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    return conn

# --- 存储文件函数 ---
def save_file_to_disk(file_type: FileType, uploaded_file):
    if file_type == FileType.AUDIOS:
        folder = os.path.join(FILE_FOLDER, "audios")
    elif file_type == FileType.IMAGES:
        folder = os.path.join(FILE_FOLDER, "images")
    else:
        raise ValueError("Invalid file type")

    """将上传的文件保存到磁盘，并返回存储路径"""
    # 生成唯一文件名，防止重名
    timestamp = int(time.time())
    filename = f"{timestamp}"
    file_path = os.path.join(folder, filename)

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path  # 返回相对路径，存入数据库

# --- 删除文件函数 ---
def delete_file_from_disk(file_type, file_path:str):
    if file_type == "audio":
        folder = os.path.join(FILE_FOLDER, "audios")
    elif file_type == "image":
        folder = os.path.join(FILE_FOLDER, "images")
    else:
        raise ValueError("Invalid file type")

    file_path = os.path.join(folder, file_path)
    os.remove(file_path)

# --- 添加消息函数 ---
def add_chat(conn, sender:str, content: Optional[str] = None, audios_path: Optional[List[str]] = None, images_path: Optional[List[str]] = None):
    cursor = conn.cursor()
    cursor.execute('''
           INSERT INTO chats (sender, content, audios_path, images_path)
           VALUES (?, ?, ?, ?)
        ''', (sender, content, audios_path, images_path))
    conn.commit()

# --- 删除消息函数 ---
def delete_message(conn, id:str):
    cursor = conn.cursor()
    cursor.execute('''
           DELETE FROM chats
           WHERE id = ?
           ''', (id,))
    conn.commit()

# --- 获取消息函数 ---
def get_chat(conn, id: Optional[str] = None):
    cursor = conn.cursor()
    if id:
        cursor.execute('''
           SELECT id, sender, content, audios_path, images_path, timestamp
           FROM chats
           WHERE id = ?
           ''', (id,))
    else:
        cursor.execute('''
           SELECT id, sender, content, audios_path, images_path, timestamp
           FROM chats
           ORDER BY timestamp
           ''')
    return cursor.fetchall()

# --- Streamlit 界面 ---
def main():
    conn = init_storage()
    add_chat(conn,  sender="user", content="你好", audios_path=['456'], images_path=['789'])
    print(get_chat(conn))

if __name__ == '__main__':
    main()