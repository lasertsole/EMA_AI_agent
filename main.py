import gradio as gr
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
messages = [systemMessage]


config={"configurable":{"session_id": "test-session"}}

humanMessage1 = HumanMessage(content="希罗和艾玛掉水里，你先救哪个？")
messages.append(humanMessage1)
for chunk in model.stream(messages, config = config):
    if chunk.content:
        print(chunk.content, end="", flush=True)
print("\n"+"-"*40)

humanMessage2 = HumanMessage(content="你怎么救")
messages.append(humanMessage2)
for chunk in model.stream(messages,config=config):
    if chunk.content:
        print(chunk.content, end="", flush=True)
print("\n"+"-"*40)

humanMessage3 = HumanMessage(content="汉娜也掉进水里了")
messages.append(humanMessage3)
for chunk in model.stream(messages,config=config):
    if chunk.content:
        print(chunk.content, end="", flush=True)
print("\n"+"-"*40)