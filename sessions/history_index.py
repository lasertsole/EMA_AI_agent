import re
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from config import SESSIONS_DIR
from typing import Any, List, Optional
from langchain.chat_models import init_chat_model

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
env_path = current_dir / '../.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

#生成模型对象
summary_LLM = init_chat_model(
    model_provider = model_provider,
    model = api_name,
    api_key = api_key,
    temperature = 0.3,
    max_retries = 2
)



# ========================
#  常量
# ========================

MAX_MESSAGE_CHARS = 1000
MAX_MESSAGES_TO_READ = 20
DEFAULT_RECENT_TURNS = 5

TIMELINE_FILE = "timeline.md"
DECISIONS_FILE = "decisions.md"
TSID_MAP_FILE = "tsid-session-map.json"

# ========================
#  类和字典
# ========================
class MessageContentItem:
    """消息内容项（多模态消息中的单个元素）"""
    type: str
    text: Optional[str]

class Message:
    """聊天消息结构"""
    role: str
    content: str | List[MessageContentItem]
    timestamp: Optional[int]

class Summary(BaseModel):
    l0: str = Field(description="一句话极简概括，10-20字，只说做了什么事，不要带任何前缀符号")
    l1: str = Field(description="如果本轮有关键技术内容，列出具体细节；如果只是闲聊/问候，输出'无'")

# L1 加载结果（按日期按需加载）
class L1DecisionsResult(BaseModel):
  available: bool
  prompt: str # L1 关键决策文本

class L0TimelineResult(BaseModel):
    available: bool
    prompt: str #L0 时间线文本，直接注入 system prompt
    rawTimeline: str # L0 原始文本（不带 XML 标签，给路由模型用）
    recentTurns: int # 分层模式下保留的最近对话轮数
    dateTsidMap: dict[str, List[str]] # 日期(YYYY-MM-DD) → 时间戳ID[] 映射
    tsidSessionMap: dict[str, str] # 时间戳ID → sessionId 映射（用于 L2 加载）


# ========================
# 工具函数
# ========================
def get_sessions_dir(agent_dir: str)-> str:
    return (Path(agent_dir) / "sessions").as_posix()

def get_decisions_path(agent_dir: str, session_id: str)-> str:
    return (Path(get_sessions_dir(agent_dir)) / session_id / DECISIONS_FILE).as_posix()

def get_timeline_path(agent_dir: str, session_id: str)-> str:
    return (Path(get_sessions_dir(agent_dir)) / session_id / TIMELINE_FILE).as_posix()

def get_tsid_map_path(agent_dir: str)-> str:
    return (Path(get_sessions_dir(agent_dir)) / TSID_MAP_FILE).as_posix()


def _session_path(session_id: str) -> str:
    return (Path(SESSIONS_DIR) / f"{session_id}/L2.json").as_posix()

def format_date()->str:
    now = datetime.now()
    year = now.year
    month = str(now.month).zfill(2)
    day = str(now.day).zfill(2)
    return f"{year}-{month}-{day}"

def read_session_messages(sessions_dir: str, session_id: str)-> str:
    """L2: 读取完整对话（内部使用）"""
    session_dir: Path = Path(sessions_dir) / f"{session_id}"
    json_path: Path = session_dir / "L2.json"

    if not json_path.exists():
        return ""

    try:
        messages = json.loads(json_path.read_text(encoding="utf-8"))
        recent = messages[-MAX_MESSAGES_TO_READ:]

        return "\n\n".join([f"{r["role"]}: {r["content"]}" for r in recent])
    except Exception:
        return ""

def parse_summary_result(raw: str)-> Summary:
    result: Summary = Summary(l0 =  "", l1 = "")

    l0_match = re.search(r'\[L0\]\s*\n([\s\S]*?)(?=\[L1\]|$)', raw)
    if l0_match:
        first_line = l0_match.group(1).strip().split("\n")[0].strip()
        if first_line:
            result.l0 = first_line

    if not result.l0:
        lines = raw.split("\n")
        for line in lines:
            line_stripped = line.strip()
            if len(line_stripped) > 0 and "[L0]" not in line_stripped and "[L1]" not in line_stripped:
                result.l0 = line_stripped
                break
            if not result.l0:
                result.l0 = "(摘要生成失败)"


    l1_match = re.search(r'\[L1\]\s*\n([\s\S]*?)$', raw)
    if l1_match:
        l1_text = l1_match.group(1).strip()
        if l1_text and l1_text != "无" and not l1_text.startswith("无"):
            result.l1 = l1_text

    return result


def parse_decisions_by_date(content: str) -> dict[str, str]:
    """解析 decisions.md，按日期分割成 Map<date, content>"""
    sections = {}

    last_date = None
    last_index = 0

    for match in re.finditer(r'^## (\d{4}-\d{2}-\d{2})$', content, re.MULTILINE):
        if last_date is not None:
            section_content = content[last_index:match.start()].strip()
            if section_content:
                existing = sections.get(last_date, "")
                sections[last_date] = existing + "\n" + section_content if existing else section_content

        last_date = match.group(1)
        last_index = match.end()

    if last_date is not None:
        section_content = content[last_index:].strip()
        if section_content:
            existing = sections.get(last_date, "")
            sections[last_date] = existing + "\n" + section_content if existing else section_content

    return sections



# ========================
# L0 解析
# ========================
def parse_tsid_from_timeline_line(line: str) -> str | None:
    """从 L0 单行中提取时间戳 ID，格式：- 202602260705 | 摘要"""
    match = re.match(r'^-\s*(\d{12})\s*\|', line)
    return match.group(1) if match else None

def date_from_tsid(tsid: str) -> str | None:
    """从时间戳 ID 中提取日期（YYYY-MM-DD 格式）"""
    if len(tsid) < 8:
        return None
    year = tsid[0:4]
    month = tsid[4:6]
    day = tsid[6:8]
    return f"{year}-{month}-{day}"

def build_date_tsid_map(timeline: str) -> dict[str, list[str]]:
    """构建 dateTsidMap：从 timeline 文本解析出日期→tsid[] 映射"""
    tsid_map = {}
    lines = [line for line in timeline.split("\n") if line.strip().startswith("-")]

    for line in lines:
        tsid = parse_tsid_from_timeline_line(line)
        if tsid:
            date = date_from_tsid(tsid)
            if date:
                if date not in tsid_map:
                    tsid_map[date] = []
                if tsid not in tsid_map[date]:
                    tsid_map[date].append(tsid)

    return tsid_map

# ========================
# L1 解析：从 decisions 文本中提取时间戳 ID
# ========================

"""
从 L1 文本中提取所有时间戳 ID
匹配格式: [202602260705]
"""
def extract_tsids(l1Text: str) -> List[str]:
    ids: List[str] = []
    regex = re.compile(r'\[(\d{12})\]')

    for match in regex.finditer(l1Text):
        tsid = match.group(1)
        if tsid and tsid not in ids:
            ids.append(tsid)

    return ids

"""
从 L0 的 dateTsidMap 中根据日期提取时间戳 ID 列表
"""
def extract_tsids_from_L0(
        l0_result: L0TimelineResult,
        dates: Optional[List[str]] = None,
) -> List[str]:
    if not dates or len(dates) == 0:
        return []

    ids: List[str] = []
    for date in dates:
        tsids = l0_result.dateTsidMap.get(date)
        if tsids:
            for tsid in tsids:
                if tsid not in ids:
                    ids.append(tsid)

    return ids

"""
给 L1 的每条决策添加 [tsid] 前缀
输入: "- 决策1\n- 决策2"
输出: "- [202602260705] 决策1\n- [202602260705] 决策2"
"""
def add_tsid_to_l1(l1_text: str, tsid: str)-> str:
    lines = "\n".split(l1_text)
    tagged = []
    for line in lines:
        trimmed = line.strip()
        if trimmed.startswith("- "):
            # 检查是否已经有 [12 位数字]
            if re.match(r'^- \[\d{12}\]', trimmed):
                tagged.append(line)
            else:
                tagged.append(re.sub(r'^(\s*- )', rf'\1[{tsid}] ', line))
        else:
            tagged.append(line)

    return "\n".join(tagged)

def safe_read_file(file_path: str)-> str:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception:
        return ""

"""
生成时间戳 ID: YYYYMMDDHHmmss（如 202602260705）
同时作为可读时间和唯一标识
"""
def generate_tsid()->str:
    now = datetime.now()
    year = now.year
    month = str(now.month).zfill(2)
    day = str(now.day).zfill(2)
    hour = str(now.hour).zfill(2)
    minute = str(now.minute).zfill(2)
    second = str(now.second).zfill(2)

    return f"{year}{month}{day}{hour}{minute}{second}"

"""
读取 tsid→sessionId 映射表
文件: history/tsid-session-map.json
格式: { "202602260705": "640b4847-...", ... }
"""
def load_tsid_session_map(agent_dir: str)-> dict[str, str]:
    map_path = Path(get_tsid_map_path(agent_dir))

    try:
        raw = map_path.read_text(encoding="utf-8")
        return json.loads(raw)
    except Exception:
        return {}

"""
保存 tsid→sessionId 映射（追加写入）
"""
def save_tsid_mapping(agent_dir: str, tsid: str, sessionId: str)-> None:
    map_path = Path(get_tsid_map_path(agent_dir))
    existing = load_tsid_session_map(agent_dir)
    existing[tsid] = sessionId
    map_path.parent.mkdir(parents=True, exist_ok=True)

    with map_path.open("w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


"""
写入：每轮结束后从 L2 生成 L0 + L1
"""
async def append_timeline_entry(
    agent_dir: str,
    session_id: str,
    tool_metas: List[str],
)-> None:
    try:
        # 总是先确保目录存在
        path = Path(_session_path(session_id))
        path.parent.mkdir(parents=True, exist_ok=True)

        tsid = generate_tsid()
        date_str = format_date()

        # 保存 tsid→sessionId 映射
        save_tsid_mapping(agent_dir, tsid, session_id)

        sessions_dir = get_sessions_dir(agent_dir)
        full_conversation = read_session_messages(sessions_dir, session_id)

        if not full_conversation:
            return

        tool_list = ", ".join(tool_metas) or "无"

        system = """你是一个技术记录助手。根据完整对话内容，生成两部分输出。使用中文。

严格按以下格式输出，不要输出任何其他内容：
L0 是时间线目录，要极度精简，像书的章节标题。注意：只输出摘要文本本身，不要输出时间戳、不要输出"- "前缀，这些由系统自动添加。

L1 是详细摘要，要包含具体的：
- 技术方案（用了什么库、什么方法）
- 文件路径、配置参数的具体值
- 代码改动（改了哪个文件、具体改了什么逻辑、为什么改）
- bug 根因和修复方式
- 确认的结论和共识

L1 每条要有足够的细节，让人不看原文也能知道具体怎么做的。每条决策用 "- " 开头，一行一条。"""
        user = f"""===== 完整对话 =====
{full_conversation}

===== 使用的工具 =====
{tool_list}

请按格式生成 [L0] 和 [L1]。"""


        summary: BaseModel = summary_LLM.with_structured_output(Summary).invoke(
            [SystemMessage(content=system), HumanMessage(content=user)],
            max_tokens = 800
        )

        if not summary and not isinstance(summary, Summary):
            raise Exception("生成L0 和 L1 时发生错误")

        # 写入 L0（代码拼接时间戳ID，不让 LLM 生成）
        if summary.l0:
            l0_summary = summary.l0
            # 去掉 LLM 可能残留的前缀
            l0_summary = re.sub(r'^-\s*', '', l0_summary)
            l0_summary = re.sub(r'^\d{12}\s*\|\s*', '', l0_summary)

            l0_line = f"- {tsid} | {l0_summary}"
            timeline_path = get_timeline_path(agent_dir, session_id)
            Path(timeline_path).parent.mkdir(parents=True, exist_ok=True)

            with open(timeline_path, "a", encoding="utf-8") as f:
                f.write(l0_line + "\n")

        # 写入 L1（每条决策添加 [tsid] 前缀）
        if summary.l1:
            l1_with_tsid = add_tsid_to_l1(summary.l1, tsid)
            decisions_path = get_decisions_path(agent_dir, session_id)
            existing = safe_read_file(decisions_path).strip()

            today_header = f"## {date_str}"

            if today_header in existing:
                with open(decisions_path, "a", encoding="utf-8") as f:
                    f.write("\n" + l1_with_tsid + "\n")
            else:
                separator = "\n\n" if len(existing) > 0 else ""
                with open(decisions_path, "a", encoding="utf-8") as f:
                    f.write(separator + today_header + "\n\n" + l1_with_tsid + "\n")

    except Exception as e:
        print(e)

"""
读取 L1（按日期/时间戳ID 按需加载）
"""

"""
从 decisions.md 中提取指定日期和/或时间戳 ID 的决策内容

decisions.md 格式：
## 2026-02-24
- [202602241600] 决策1
- [202602241600] 决策2

## 2026-02-26
- [202602260705] 决策3

过滤优先级：
1. 如果指定了 tsids，精确匹配包含这些时间戳 ID 的条目
2. 如果指定了 dates，加载整个日期段
3. 都不指定则加载全部
"""
async def load_l1_decisions(
  agent_dir: str,
  # 指定要加载的日期列表
  dates: Optional[List[str]],
  # 指定要加载的时间戳 ID 列表（更精确的过滤）
  tsids: Optional[List[str]],
)-> L1DecisionsResult:
    decisions_path = get_decisions_path(agent_dir)
    full_content = safe_read_file(decisions_path).strip()

    if full_content is None:
        return L1DecisionsResult(available=False, prompt="")


    # 优先按时间戳 ID 过滤（最精确）
    if tsids and len(tsids) > 0:
        tsid_set = set(tsids)
        filtered_lines: List[str] = []
        current_date_header = ""

        for line in full_content.split("\n"):
            trimmed = line.strip()

            if re.match(r'^## \d{4}-\d{2}-\d{2}$', trimmed):
                current_date_header = trimmed
                continue


            tsid_match = re.search(r'\[(\d{12})\]', trimmed)
            if tsid_match and tsid_match.group(1) in tsid_set:
                if current_date_header and current_date_header not in filtered_lines:
                    if len(filtered_lines) > 0:
                        filtered_lines.append("")
                    filtered_lines.append(current_date_header)
                    filtered_lines.append("")
                filtered_lines.append(trimmed)

        if len(filtered_lines) == 0:
            return L1DecisionsResult(available=False, prompt="")

        filtered_content = "\n".join(filtered_lines)
        prompt = f"<key_decisions>\n以下是相关时间点的关键决策和技术细节：\n{filtered_content}\n</key_decisions>"
        return L1DecisionsResult(available=True, prompt=prompt)

    # 按日期过滤
    if dates and len(dates) > 0:
        requested_dates = set(dates)
        sections = parse_decisions_by_date(full_content)
        matched = []

        for date, content in sections.items():
            if date in requested_dates:
                matched.append(f"## {date}\n\n{content}")

        if len(matched) == 0:
            dates_str = ", ".join(dates)
            return {"available": False, "prompt": ""}

        filtered_content = "\n\n".join(matched)
        dates_str = ", ".join(dates)
        prompt = f"<key_decisions>\n以下是 {dates_str} 的关键决策和技术细节：\n{filtered_content}\n</key_decisions>"
        return {"available": True, "prompt": prompt}

    # 无过滤，加载全部
    prompt = f"<key_decisions>\n以下是历史对话中提取的关键决策和技术细节：\n{full_content}\n</key_decisions>"
    return {"available": True, "prompt": prompt}
# ========================
# 读取 L0（始终加载）
# ========================


async def load_l0_timeline(agent_dir: str, session_id: str) -> dict[str, Any]:
    """读取 L0（始终加载）"""
    timeline_path = get_timeline_path(agent_dir, session_id)
    timeline = safe_read_file(timeline_path).strip()

    if not timeline:
        return {
            "available": False,
            "prompt": "",
            "raw_timeline": "",
            "recent_turns": DEFAULT_RECENT_TURNS,
            "date_tsid_map": {},
            "tsid_session_map": {},
        }

    date_tsid_map = build_date_tsid_map(timeline)
    tsid_session_map = load_tsid_session_map(agent_dir)

    prompt = f"<conversation_timeline>\n以下是历史对话的时间线索引：\n{timeline}\n </conversation_timeline>"

    return {
        "available": True,
        "prompt": prompt,
        "raw_timeline": timeline,
        "recentTurns": DEFAULT_RECENT_TURNS,
        "date_tsid_map": date_tsid_map,
        "tsid_session_map": tsid_session_map,
    }

async def load_layered_history(
    agent_dir: str,
) -> dict[str, Any]:
    l0 = await load_l0_timeline(agent_dir=agent_dir)
    return {
        "enabled": l0["available"],
        "prompt": l0["prompt"],
        "recent_turns": l0["recent_turns"],
    }