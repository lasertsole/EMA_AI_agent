import asyncio
from pathlib import Path
from sessions.history_index import append_timeline_entry

current_dir = Path(__file__).parent.resolve()

async def main():
    print(await append_timeline_entry(agent_dir=current_dir.as_posix(), session_id='1', tool_metas=[]))

if __name__ == "__main__":
    asyncio.run(main())