import asyncio
import json
import threading
import time
from pathlib import Path
from bus import MessageBus
from config import ROOT_DIR
from channels.manager import ChannelManager

channels_json = Path(ROOT_DIR) / "channels.json"
config = json.loads(channels_json.read_text())

bus = MessageBus()
channel_manager = ChannelManager(config, bus)

async def main():
    threading.Thread(target=lambda: channel_manager.start_all(), daemon=True).start()
    qq_channel = channel_manager.get_channel("qq")

    while True:
        msg = await qq_channel.bus.consume_inbound()

async def stop():
    threading.Thread(target=lambda: channel_manager.start_all(), daemon=True).start()
    time.sleep(3)
    await channel_manager.stop_all()


if __name__ == "__main__":
    # asyncio.run(main())
    asyncio.run(stop())