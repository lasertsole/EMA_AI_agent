import asyncio
from pathlib import Path
from tools import ALL_TOOLS
from workspace import ALL_FILE_NAMES
from skills.loader import scan_skills
from viking_router import viking_route, build_skill_names_only_prompt
from sessions.history_index import load_l0_timeline, load_l1_decisions, load_l2_session

current_dir = Path(__file__).parent.resolve()

async def main():
    # ===== L0 时间线加载（始终） start =====
    l0_result = await load_l0_timeline(session_id='1')
    # ===== L0 时间线加载（始终） end =====

    # ===== viking routing start =====
    route_result = await viking_route(
        user_message = "雪莉嫁给我如何？",
        tools = [t.name for t in ALL_TOOLS],
        file_names = ALL_FILE_NAMES,
        timeline = l0_result['raw_timeline'],
        skills = scan_skills()
    )
    # ===== viking routing end =====

    if route_result["skipped"]:
        return None

    context:str = ""
    # ===== L1 按日期按需加载 start =====
    if route_result["needs_l1"]:
        l1_prompt = load_l1_decisions(session_id='1', dates=route_result["l1_dates"], tsids=route_result["l1_tsids"])

        if l1_prompt is not None and l1_prompt.available and len(l1_prompt.prompt)> 0:
            context += "\n\n" + l1_prompt.prompt
    # ===== L1 按日期按需加载 end =====

    # ===== L2 按需加载 start =====
    if route_result["needs_l2"]:
        l2_prompt = load_l2_session(session_id='1', tsids = route_result["l1_tsids"])

        if l2_prompt is not None and l2_prompt.available and len(l2_prompt.prompt)> 0:
            context += "\n\n" + l2_prompt.prompt
    # ===== L2 按需加载 end =====

    print(route_result)
    print({
        "tools": route_result["tools"],
        "files": route_result["files"],
        "context": context,
    })
    return context

if __name__ == "__main__":
    asyncio.run(main())