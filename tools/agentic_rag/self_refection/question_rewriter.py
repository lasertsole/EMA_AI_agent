import os
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
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

system = """You a question re-writer that converts an input question to a better version that is optimized \n 
     for vectorstore retrieval. Look at the input and try to reason about the underlying sematic intent / meaning."""
re_write_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        ("human", "Here is the initial question: \n\n {question} \n Formulate an improved question."),
    ]
)

question_rewriter = re_write_prompt | init_chat_model(
        model_provider = model_provider,
        model = api_name,
        api_key = api_key,
        temperature = 0,
        max_retries = 2
    ) | StrOutputParser()