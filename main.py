from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages

# 定义状态图
graph = StateGraph()
graph.add_node("chatbot", lambda state: {"response": "Hello!"})
graph.add_edge(START, "chatbot")

# 编译并运行
app = graph.compile()
response = app.invoke({"messages": []})
print(response["response"])  # 输出: Hello!


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press F9 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
