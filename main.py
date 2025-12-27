import os
import warnings
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_deepseek import ChatDeepSeek
from langchain.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Field name.*shadows an attribute in parent"
)


with open("personality.txt", "r", encoding="utf-8") as f:
    personality = f.read()

# 加载环境变量
load_dotenv()

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

#生成模型对象
model = ChatDeepSeek(
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=0.7,
    max_retries = 2
)

# 线程记忆功能
checkpoint = InMemorySaver()
# 联网搜索功能
tavily_api_key = os.getenv("TAVILY_API_KEY")
web_search = TavilySearch(tavily_api_key=tavily_api_key, max_results = 7)

#生成agent对象
agent = create_agent(
    model=model,
    tools=[web_search],
    system_prompt=personality,
    checkpointer=checkpoint,
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
    full_reply = ""  # 存储完整回复，用于更新上下文
    current_ai_reply = ""  # 临时存储当前AI回复片段

    for chunk in agent.stream(
            {"messages": message_history},  # 传入完整上下文
            config=config,
            stream_mode="values"  # 指定流式模式为「值」（更易解析）
    ):
        # 解析 chunk 中的 messages 字段（Agent 流式返回的核心内容）
        if "messages" in chunk and len(chunk["messages"]) > 0:
            # 获取最新的消息片段
            latest_msg = chunk["messages"][-1]
            # 仅处理 AI 回复（过滤工具调用/系统消息等）
            if isinstance(latest_msg, AIMessage) and latest_msg.content:
                # 提取新增的回复内容（避免重复打印）
                new_content = latest_msg.content[len(current_ai_reply):]
                if new_content:
                    print(new_content, end="", flush=True)
                    current_ai_reply = latest_msg.content
                    full_reply = current_ai_reply

    # 将完整的 AI 回复添加到上下文（保证多轮对话连贯）
    if full_reply:
        message_history.append(AIMessage(content=full_reply))

    # 分隔线（美化输出）
    print("\n" + "-" * 40)