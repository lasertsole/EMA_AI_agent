import json
import botpy
from pathlib import Path
from config import ROOT_DIR
from botpy.message import C2CMessage

# 自定义机器人客户端
class MyClient(botpy.Client):
    async def on_c2c_message_create(self, message: C2CMessage):
        print(message.content)
        await message.reply(content="C2C消息收到啦！")



# 配置消息意图（必须开启，否则收不到消息）
intents = botpy.Intents(public_guild_messages=True, direct_message=True)
# 初始化并运行
client = MyClient(intents= botpy.Intents.default())

def main():
    channels_json = Path(ROOT_DIR) / "channels.json"
    if not channels_json.exists():
        return

    channels = json.loads(channels_json.read_text())
    qq_config = channels["qq"]
    client.run(
        appid=qq_config["appId"],
        secret=qq_config["secret"],  # 新版用secret，不是token
    )

if __name__ == "__main__":
    main()
