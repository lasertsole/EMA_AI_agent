import asyncio
from pathlib import Path
from tools import ALL_TOOLS
from workspace import CORE_FILE_NAMES
from skills.loader import scan_skills
from viking_router import viking_route
from sessions.history_index import load_l0_timeline, load_l1_decisions, add_tsid_to_l1

current_dir = Path(__file__).parent.resolve()

async def main():
    l0_result = await load_l0_timeline(agent_dir=current_dir.as_posix(), session_id='1')
    print(add_tsid_to_l1(l1_text="""
    - 具体步骤：第一步寻找彩叶本人或手镯，第二步获取手镯，第三步激活手镯连接月读世界
    - 搜索策略：先询问相关人员，搜索实验室位置，寻找活动痕迹，重点搜索东京科技园区、大学机械工程系、义体技术研究中心
    - 时间线分析：发现辉夜等待八千年与彩叶是现代人的矛盾，推测月读世界时间流速不同或手镯有时空功能
    - 备用方案：寻找月读世界其他入口，联系其他知道月读世界的人，使用魔法少女特殊能力
    """, tsid="20260314203504")
    )
    # print(await load_l1_decisions(agent_dir = current_dir.as_posix(), session_id = '1'))

if __name__ == "__main__":
    asyncio.run(main())