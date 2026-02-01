import os
from typing import List
from pathlib import Path
from dotenv import load_dotenv
from operator import itemgetter
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
env_path = current_dir / '../../../../.env'
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

# Prompt
template = """Here is the question you need to answer:

\n --- \n {question} \n --- \n

Here is any available background question + answer pairs:

\n --- \n {q_a_pairs} \n --- \n

Here is additional context relevant to the question: 

\n --- \n {context} \n --- \n

Use the above context and any background question + answer pairs to answer the question: \n {question}
"""

decomposition_prompt = ChatPromptTemplate.from_template(template)

def format_qa_pair(question, answer):
    """Format Q and A pair"""

    formatted_string = ""
    formatted_string += f"Question: {question}\nAnswer: {answer}\n\n"
    return formatted_string.strip()


# llm
llm = init_chat_model(
    model_provider = model_provider,
    model = api_name,
    api_key = api_key,
    temperature = 0,
    max_retries = 2
)

def answer_recursively(questions: List[str], retriever):
    q_a_pairs = ""
    for q in questions:
        rag_chain = (
                {"context": itemgetter("question") | retriever,
                 "question": itemgetter("question"),
                 "q_a_pairs": itemgetter("q_a_pairs")}
                | decomposition_prompt
                | llm
                | StrOutputParser())

        answer = rag_chain.invoke({"question": q, "q_a_pairs": q_a_pairs})
        q_a_pair = format_qa_pair(q, answer)
        q_a_pairs = q_a_pairs + "\n---\n" + q_a_pair