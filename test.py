import asyncio
from pathlib import Path
from sessions.history_index import get_timeline_path, load_l0_timeline, load_l1_decisions

current_dir = Path(__file__).parent.resolve()

async def main():
    print(get_timeline_path(current_dir.as_posix()))
    print(await load_l0_timeline(current_dir.as_posix()))
    # print(await load_l1_decisions({"agent_dir": current_dir, "dates": routingDecision.l1Dates})

if __name__ == "__main__":
    asyncio.run(main())