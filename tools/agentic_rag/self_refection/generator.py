import os
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量和模型初始化（同上）
env_path = current_dir / '../../../.env'
env_path = env_path.resolve()

load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")


# Prompt
systemPrompt = """
You are a Q&A assistant.
When responding to the user's question, you shall base your answer on the provided contextual information.
If any part of the context is irrelevant to question,please disregard it.
All content of the answer must be consistent with the actual facts in the context,
 and any fabrication of unsubstantiated facts is prohibited.
"""
generate_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", systemPrompt),
        ("human", "Retrieved document: \n\n {documents} \n\n User question: {question}"),
    ]
)

# Chain
generator = generate_prompt | init_chat_model(
        model_provider = model_provider,
        model = api_name,
        api_key = api_key,
        temperature = 0,
        max_retries = 2
    ) | StrOutputParser()