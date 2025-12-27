import os
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langchain_deepseek import ChatDeepSeek
from langchain.messages import HumanMessage
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

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

#推理模型
reasoner_model = ChatDeepSeek(
    model='deepseek-reasoner',
    api_key= deepseek_api_key,
    temperature=0.3,
    max_retries = 2
)

#消息汇总模型
summary_model = ChatDeepSeek(#对话模型
    model='deepseek-chat',
    api_key= deepseek_api_key,
    temperature=0.4,
    max_retries = 2
)

# 线程记忆功能
checkpoint = InMemorySaver()

# 联网搜索功能
tavily_api_key = os.getenv("TAVILY_API_KEY")
web_search = TavilySearch(tavily_api_key=tavily_api_key, max_results = 7)

# 上下文摘要压缩，用于无限对话
summarizationMiddleware = SummarizationMiddleware(
    model = summary_model,
    trigger = ('tokens', 3000),#超过3000token触发摘要
    keep = ('messages', 10),#摘要后保留最近10条消息
)

def _get_last_user_text(messages) -> str:
    """从消息队列中取最近一条用户消息文本（无则返回空串）"""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else ""
    return ""

@wrap_model_call
def dynamic_model_routing(request: ModelRequest, handler) -> ModelResponse:
    """
    根据对话复杂度动态选择 DeepSeek 模型:
    - 复杂：deepseek-reasoner
    - 简单：deepseek-chat
    """
    messages = request.state.get("messages", [])
    msg_count = len(messages)
    last_user = _get_last_user_text(messages)
    last_len = len(last_user)

    # 一些“复杂任务”关键词（可按需扩充）
    hard_keywords = ("证明", "推导", "严谨", "规划", "多步骤", "chain of thought", "step-by-step","reason step-by-step", "数学", "逻辑证明", "约束求解")

    # 简单的复杂度启发式:
    # 1) 历史消息较长 2)最近用户输入很长 3) 出现复杂任务关键词
    is_hard = (
        msg_count > 10 or
        last_len > 120 or
        any(kw.lower() in last_user.lower() for kw in hard_keywords)
    )

    # 选择模型
    request.override(model=reasoner_model) if is_hard else basic_model

    return handler(request)

#生成agent对象
agent = create_agent(
    model=basic_model,
    tools=[web_search],
    system_prompt=personality,
    checkpointer=checkpoint,
    middleware=[dynamic_model_routing, summarizationMiddleware],
)

config={"configurable":{"thread_id": 1}}
message_history=[]

print("汉娜さん，有什么要找我说的吗？（输入 exit/e/quit/q 退出）")

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

    # 分隔线（美化输出）
    print("\n" + "-" * 40)