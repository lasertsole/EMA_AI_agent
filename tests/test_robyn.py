import requests
from typing import List
from langchain_core.messages import BaseMessage, messages_to_dict

session_id = '1'

def main()->None:
    messages: List[BaseMessage] = []

    with requests.post("http://127.0.0.1:8080/events/async", stream=True, json=messages_to_dict(messages)) as response:
        for line in response.iter_lines():
            if line:
                decoded_line:str = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    content = decoded_line[6:]
                    print(f"content: {content}")
                elif decoded_line.startswith("event: "):
                    print(f"event: {decoded_line[7:]}")

if __name__ == "__main__":
    main()