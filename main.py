from langchain_deepseek import ChatDeepSeek
from dotenv import load_dotenv
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import os

with open("personality.txt", "r", encoding="utf-8") as f:
    personality = f.read()

# 加载环境变量
load_dotenv()

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

llm = ChatDeepSeek(
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=0.7,
    max_retries = 2
)


prompt = ChatPromptTemplate.from_messages([
    ("system", personality),
    MessagesPlaceholder(variable_name="history"),
    ("human","{input}")
])

chain = prompt | llm

#多轮对话
message_history = InMemoryChatMessageHistory()



chain_with_history = RunnableWithMessageHistory(
    chain,
    lambda session_id: message_history,
    input_messages_key="input",
    history_messages_key="history",
)

session_id = "test-session"

response1 = chain_with_history.invoke(
    {"input": "希罗和艾玛掉水里，你先救哪个？"},
    config={"configurable":{
        "session_id": session_id
    }
})
print(response1.content)

response2 = chain_with_history.invoke(
    {"input": "你怎么救？"},
    config={"configurable":{
        "session_id": session_id
    }
})
print(response2.content)

response3 = chain_with_history.invoke(
    {"input": "汉娜也掉进水里了"},
    config={"configurable":{
        "session_id": session_id
    }
})
print(response3.content)

#流式返回
# response = llm.invoke(prompt)
# print(response.content)
# for chunk in llm.stream(messages):
#     print(chunk.content,end='\n')