from typing import Any

def process_sse_data(data: Any)-> str:
    res:str = ""
    if data:
        decoded_line: str = data if isinstance(data, str) else data.decode()
        if decoded_line.startswith("data: "):
            res = decoded_line[6:].strip()

    return res