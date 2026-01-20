import os
import asyncio
from typing import Any
from dotenv import load_dotenv
from langchain.messages import HumanMessage, AIMessage, RemoveMessage, AIMessageChunk
from agent import agent

async def main():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './.env')
    load_dotenv(env_path, override=True)

    is_stream = os.getenv("IS_STREAM")

    config = {"configurable": {"thread_id": 1}}

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
        message_history = []
        message_history.append(user_msg)
        print("橘雪莉：", end="", flush=True)

        if is_stream == 'True':
            async for chunk in agent.astream({"messages":message_history}, config=config, stream_mode="messages"):
                msg_chunk: AIMessageChunk = chunk[0]
                event_chunk: dict[str, Any] = chunk[1]

                if (isinstance(msg_chunk, AIMessageChunk)
                        and event_chunk.get("langgraph_node") == 'model'
                        and len(msg_chunk.content)>0):
                    print(msg_chunk.content, flush=True, end="")
        else:
            result = await agent.ainvoke({"messages":message_history}, config=config )
            print(result["messages"][-1].content)
        # 分隔线（美化输出）
        print("\n" + "-" * 40)

# 运行异步主函数
if __name__ == "__main__":
    asyncio.run(main())