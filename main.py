import asyncio
from langchain.messages import HumanMessage
from agent import agent

async def main():
    config = {"configurable": {"thread_id": 1}}
    message_history = []

    print("汉娜さん，来茶间聊天吧！（输入 exit/e/quit/q 退出）")
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
        result = await agent.ainvoke({"messages":message_history}, config=config )
        print(result["messages"][-1].content)
        message_history=result["messages"]
        # 分隔线（美化输出）
        print("\n" + "-" * 40)

# 运行异步主函数
if __name__ == "__main__":
    asyncio.run(main())