import os
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langchain_deepseek import ChatDeepSeek
from langchain.messages import HumanMessage
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from middleWare import dynamic_model_routing

with open("personality.txt", "r", encoding="utf-8") as f:
    personality = f.read()

# 加载环境变量
load_dotenv(override = True)

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

#生成模型对象
basic_model = ChatDeepSeek(#对话模型
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=0.7,
    max_retries = 2
)

#消息汇总模型
summary_model = ChatDeepSeek(#对话模型
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=0.4,
    max_retries = 2
)

#推理模型
# reasoner_model = ChatDeepSeek(
#     model='deepseek-reasoner',
#     api_key= deepseek_api_key,
#     temperature=0.3,
#     max_retries = 2
# )

# 线程记忆功能
checkpoint = InMemorySaver()

# 联网搜索功能
tavily_api_key = os.getenv("TAVILY_API_KEY")
web_search = TavilySearch(tavily_api_key=tavily_api_key, max_results = 7)

# 上下文摘要压缩，用于无限对话
summarizationMiddleware = SummarizationMiddleware(
    model=summary_model,
    max_tokens_before_summary= 50,#超过3000token触发摘要
    messages_to_keep=1,            #摘要后保留最近10条消息
)

dynamicModelRouting = dynamic_model_routing()

#生成agent对象
agent = create_agent(
    model=basic_model,
    tools=[web_search],
    system_prompt=personality,
    checkpointer=checkpoint,
    middleware=[summarizationMiddleware],
)

config={"configurable":{"thread_id": 1}}
message_history=[]

print("汉娜桑，有什么要找我说的吗？（输入 exit/e/quit/q 退出）")

while True:
    # 获取用户输入
    user_input = input("远野汉娜: ").strip()
    if user_input.lower() in {"exit", "e", "quit", "q"}:
        print("对话结束～")
        break
    if not user_input:
        print("橘雪莉：请输入有效的问题哦～")
        continue

    # 添加用户消息到上下文
    user_msg = HumanMessage(content=user_input)
    message_history.append(user_msg)

    print("橘雪莉：", end="", flush=True)
    result = agent.invoke({"messages":message_history}, config=config )
    print(result["messages"][-1].content)
    message_history=result["messages"]
    print(message_history)

    # 分隔线（美化输出）
    print("\n" + "-" * 40)