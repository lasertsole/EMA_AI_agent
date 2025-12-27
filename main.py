from langchain_deepseek import ChatDeepSeek
from langchain.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
import os

with open("personality.txt", "r", encoding="utf-8") as f:
    personality = f.read()

# 加载环境变量
load_dotenv()

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

model = ChatDeepSeek(
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=0.7,
    max_retries = 2
)

systemMessage = SystemMessage(content=personality)

config={"configurable":{"session_id": "test-session"}}
messages = [systemMessage]

print("汉娜桑，有什么要找我说的吗？")
while True:
    user_input = input("汉娜:")
    if user_input.lower() in {"exit","e","quit","q"}:
        print("对话结束")
        break

    messages.append(HumanMessage(content=user_input))

    print("橘雪莉：",end="",flush=True)
    full_reply = ""
    for chunk in model.stream(messages,config=config):
        if chunk.content:
            print(chunk.content, end="", flush=True)
            full_reply+=chunk.content
    print("\n" + "-" * 40)

    messages.append(AIMessage(content=user_input))
    messages = messages[-50:]