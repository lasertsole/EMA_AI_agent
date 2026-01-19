import os
import asyncio
from dotenv import load_dotenv
from langchain.messages import HumanMessage, AIMessage, RemoveMessage, AIMessageChunk
from agent import agent

async def main():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), './.env')
    load_dotenv(env_path, override=True)

    is_stream = os.getenv("IS_STREAM")

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

        if is_stream == 'True':
            merge_AI_message_chunk = AIMessageChunk(content="")
            async for chunk in agent.astream({"messages":message_history}, config=config, stream_mode="messages" ):
                msg_chunk:AIMessageChunk = chunk[0]
                event_dict = chunk[1]
                langgraph_node = event_dict.get("langgraph_node")

                if isinstance(msg_chunk, AIMessageChunk) and langgraph_node == 'model':
                    merge_AI_message_chunk += msg_chunk
                    content = msg_chunk.content
                    print(content,flush=True, end="")

                    if msg_chunk.chunk_position == "last":
                        ai_msg = AIMessage(
                            content = merge_AI_message_chunk.content,
                            usage_metadata = merge_AI_message_chunk.usage_metadata,
                            response_metadata = merge_AI_message_chunk.response_metadata,
                            tool_calls = merge_AI_message_chunk.tool_calls
                        )
                        message_history.append(ai_msg)
                elif isinstance(msg_chunk, RemoveMessage):
                    remove_id = msg_chunk.id
                    if remove_id == "__remove_all__":
                        message_history = []
                    else:
                        message_history = [msg for msg in message_history if msg["id"] != remove_id]
                else:
                    message_history.append(msg_chunk)

        else:
            result = await agent.ainvoke({"messages":message_history}, config=config )
            print(result["messages"][-1].content)
            message_history=result["messages"]
        # 分隔线（美化输出）
        print("\n" + "-" * 40)

# 运行异步主函数
if __name__ == "__main__":
    asyncio.run(main())