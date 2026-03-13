import asyncio
from pathlib import Path
from tools import ALL_TOOLS
from workspace import CORE_FILE_NAMES
from skills.loader import scan_skills
from sessions.viking_router import viking_route
from sessions.history_index import append_timeline_entry, load_l0_timeline, load_l1_decisions

current_dir = Path(__file__).parent.resolve()

async def main():
    #print(await append_timeline_entry(agent_dir=current_dir.as_posix(), session_id='1', tool_metas=[]))
    # l0_result = await load_l0_timeline(agent_dir=current_dir.as_posix(), session_id='1')
    # print(await viking_route(
    #     prompt="八千代是谁",
    #     tools=[
    #         tool.name for tool in ALL_TOOLS
    #     ],
    #     file_names=CORE_FILE_NAMES,
    #     skills = scan_skills(),
    #     timeline=l0_result['raw_timeline']),
    # )
    print(await load_l1_decisions(agent_dir =current_dir.as_posix(), session_id='1'))

if __name__ == "__main__":
    asyncio.run(main())