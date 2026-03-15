import asyncio
from pathlib import Path
from tools import ALL_TOOLS
from workspace import ALL_FILE_NAMES
from skills.loader import scan_skills
from viking_router import viking_route
from sessions.history_index import load_l0_timeline, load_l1_decisions, load_l2_session

current_dir = Path(__file__).parent.resolve()

async def main():
    l0_result = await load_l0_timeline(agent_dir=current_dir.as_posix(), session_id='1')
    route_result = await viking_route(
        user_message="雪莉嫁给我如何？",
        tools=[t.name for t in ALL_TOOLS],
        file_names=ALL_FILE_NAMES,
        timeline=l0_result['raw_timeline'],
        skills=scan_skills()
    )

    # ===== L0 时间线加载（始终） start =====
    l0_result = await load_l0_timeline(session_id='1')
    print(l0_result["date_tsid_map"])
    # ===== L0 时间线加载（始终） end =====

    # ===== L1 按日期按需加载 start =====
    if route_result["needs_l1"]:
        l1_prompt = await load_l1_decisions(session_id='1', dates=route_result["l1_dates"], tsids=route_result["l1_tsids"])
    # ===== L1 按日期按需加载 end =====

    # ===== L2 按需加载 start =====
    if route_result["needs_l2"]:
        l2_prompt = await load_l2_session(l0_result["date_tsid_map"])
        print(l2_prompt)
    # ===== L2 按需加载 end =====

if __name__ == "__main__":
    asyncio.run(main())