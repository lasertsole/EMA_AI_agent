import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量和模型初始化（同上）
env_path = current_dir / '../../../.env'
env_path = env_path.resolve()

load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

class GradeHallucinations(BaseModel):
    """Binary score for hallucination present in generation answer."""

    binary_score: str = Field(description="Answer is grounded in the facts, 'yes' or 'no'")

# LLM with function call
structured_llm_grader = init_chat_model(
        model_provider = model_provider,
        model = api_name,
        api_key = api_key,
        temperature = 0,
        max_retries = 2
    ).with_structured_output(GradeHallucinations)

# Prompt
system = """You are a grader assessing whether an LLM generation is grounded in / supported by a set of retrieved facts. \n 
     Give a binary score 'yes' or 'no'. 'Yes' means that the answer is grounded in / supported by the set of facts."""
hallucination_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        ("human", "Set of facts: \n\n {documents} \n\n LLM generation: {generation}"),
    ]
)

hallucination_grader = hallucination_prompt | structured_llm_grader