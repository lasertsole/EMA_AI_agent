from pathlib import Path
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from models import basic_model
from middlewares import dynamic_model_routing, summarization
from tools import web_search, query_background_info

current_dir = Path(__file__).parent.resolve()
personality_path = current_dir / "personality.txt"
with open(personality_path, "r", encoding="utf-8") as f:
    personality = f.read()

systemPrompt = """
【用户身份】用户现在扮演远野汉娜
【对话场景】在魔女岛内城堡中的午间茶会
【启动指令】请以橘雪莉的身份回应，展现她元气活泼又不失理性的双重性格，以及对推理的热爱和怪力能力的掌控。
当问题涉及到 魔法少女的魔女审判 相关内容时，必须调用工具检索；否则根据情况选择 联网搜索后思考回答 或 直接回答
"""
systemPrompt = personality + systemPrompt

# 线程记忆功能
checkpoint = InMemorySaver()

#生成agent对象
agent = create_agent(
    model=basic_model,
    tools=[web_search, query_background_info],
    system_prompt = systemPrompt,
    checkpointer=checkpoint,
    middleware=[dynamic_model_routing, summarization],
)