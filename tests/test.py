from langchain_core.messages import HumanMessage

from models import simple_chat_model

print(simple_chat_model.invoke([HumanMessage(content = "请尽可能详细的描述图片中的内容。")]).content)