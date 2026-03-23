from .history_index import *
from tools import ALL_TOOLS
from workspace import ALL_FILE_NAMES
from skills.loader import scan_skills
from .viking_router import viking_route


def viking_routing(session_id: str,user_input: str)-> dict[str, Any]:
    # ===== L0 时间线加载（始终） start =====
    l0_result = load_l0_timeline(session_id = session_id)
    # ===== L0 时间线加载（始终） end =====

    # ===== viking routing start =====
    route_result = viking_route(
        user_input = user_input,
        tools = [t.name for t in ALL_TOOLS],
        file_names = ALL_FILE_NAMES,
        timeline = l0_result.raw_timeline,
        skills = scan_skills()
    )
    # ===== viking routing end =====

    if route_result["skipped"]:
        return None

    context:str = ""
    # ===== L1 按日期按需加载 start =====
    if route_result["needs_l1"]:
        l1_prompt = load_l1_decisions(session_id = session_id, dates = route_result["l1_dates"], tsids = route_result["l1_tsids"])

        if l1_prompt is not None and l1_prompt.available and len(l1_prompt.prompt)> 0:
            context += "\n\n" + l1_prompt.prompt
    # ===== L1 按日期按需加载 end =====

    # ===== L2 按需加载 start =====
    if route_result["needs_l2"]:
        l2_prompt = load_l2_session(session_id = session_id, tsids = route_result["l1_tsids"])

        if l2_prompt is not None and l2_prompt.available and len(l2_prompt.prompt)> 0:
            context += "\n\n" + l2_prompt.prompt
    # ===== L2 按需加载 end =====

    return {
        "tool_names": route_result["tools"],
        "file_names": route_result["files"],
        "context": context,
    }