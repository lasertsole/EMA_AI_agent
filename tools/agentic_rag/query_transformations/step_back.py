import os
from pathlib import Path
from dotenv import load_dotenv
from typing import TypedDict
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量和模型初始化（同上）
env_path = current_dir / '../../../.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

examples = [
    {
        "input": "Could the members of The Police perform lawful arrests?",
        "output": "what can the members of The Police do?",
    },
    {
        "input": "Jan Sindel’s was born in what country?",
        "output": "what is Jan Sindel’s personal history?",
    },
]
# We now transform these to example messages
example_prompt = ChatPromptTemplate.from_messages(
    [
        ("human", "{input}"),
        ("ai", "{output}"),
    ]
)
few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    examples=examples,
)
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert at world knowledge. Your task is to step back and paraphrase a question to a more generic step-back question, which is easier to answer. Here are a few examples:""",
        ),
        # Few shot examples
        few_shot_prompt,
        # New question
        ("user", "{question}"),
    ]
)

generate_query_step_back = prompt | init_chat_model(
    model_provider = model_provider,
    model = api_name,
    api_key = api_key,
    temperature = 0,
    max_retries = 2
) | StrOutputParser()

class GraphState(TypedDict):
    input: str  # 原问题(输入)
    output: str  # 变换后的问题

def build_step_back_graph():
    async def generate_query_step_back(state: GraphState):
        return await generate_query_step_back.ainvoke({"question": state["input"]})

    workflow = StateGraph(GraphState)

    workflow.add_node("generate_query_step_back_node", generate_query_step_back)

    workflow.add_edge(START, "generate_query_step_back_node")
    workflow.add_edge("generate_query_step_back_node", END)

    generate_query_step_back_graph = workflow.compile()

    return generate_query_step_back_graph