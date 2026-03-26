import json

from websocket import create_connection
session_id = '1'

def main() -> None:
    # 连接到 Robyn 服务器的 websocket 端点
    ws = create_connection("ws://127.0.0.1:8080/ws")

    try:
        # 持续通信示例
        while True:
            obj = {
                "abc": "hellow",
            }
            print(obj)
            send_obj = {
                "session_id": session_id,
                "event": "message",
                "content": obj
            }
            print(send_obj)
            message = input("输入消息 (输入 'quit' 退出): ")
            if message.lower() == 'quit':
                break
            ws.send(json.dumps(send_obj))
            response = ws.recv()
            print(f"服务器回复：{response}")

    except KeyboardInterrupt:
        print("\n客户端断开连接")
    finally:
        ws.close()


if __name__ == "__main__":
    main()