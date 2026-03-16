import re
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from config import SESSIONS_DIR, ROOT_DIR
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

HISTORY_FILE = "history.jsonl"
TIMELINE_FILE = "timeline.md"
DECISIONS_FILE = "decisions.md"
SUMMARY_FILE = "summary.md"

L2_MAX_MESSAGES_PER_SESSION = 30 # L2 加载限制：每个 session 最多读取的消息数
L2_MAX_CHARS_PER_MESSAGE = 2000 # L2 加载限制：每条消息最大字符数
L2_MAX_SESSIONS = 2 # L2 加载限制：最多加载的 session 数
L2_MAX_TOTAL_CHARS = 12000 # L2 加载限制：总输出最大字符数（约 4000 tok）

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
    l1: List[str] = Field(description="如果本轮有关键步骤内容，列出具体细节.如果没有步骤信息，则不输出", examples= [[
        "- 具体步骤：第一步寻找彩叶本人或手镯，第二步获取手镯，第三步激活手镯连接月读世界",
        "- 搜索策略：先询问相关人员，搜索实验室位置，寻找活动痕迹，重点搜索东京科技园区、大学机械工程系、义体技术研究中心",
        "- 时间线分析：发现辉夜等待八千年与彩叶是现代人的矛盾，推测月读世界时间流速不同或手镯有时空功能",
        "- 备用方案：寻找月读世界其他入口，联系其他知道月读世界的人，使用魔法少女特殊能力",
    ]])

# L0 加载结果
class L0TimelineResult(BaseModel):
    available: bool
    prompt: str #L0 时间线文本，直接注入 system prompt
    rawTimeline: str # L0 原始文本（不带 XML 标签，给路由模型用）
    recentTurns: int # 分层模式下保留的最近对话轮数
    dateTsidMap: dict[str, List[str]] # 日期(YYYY-MM-DD) → 时间戳ID[] 映射
    tsidSessionMap: dict[str, str] # 时间戳ID → sessionId 映射（用于 L2 加载）

# L1 加载结果（按日期按需加载）
class L1DecisionsResult(BaseModel):
  available: bool
  prompt: str # L1 关键决策文本

# L2 加载结果（按需加载）
class L2SessionResult(BaseModel):
  available: bool
  prompt: str # L2 完整对话文本


# ========================
# 工具函数
# ========================
def get_sessions_dir(agent_dir: str)-> str:
    return (Path(agent_dir) / "sessions").as_posix()

def get_history_path(agent_dir: str, session_id: str)-> str:
    return (Path(get_sessions_dir(agent_dir)) / session_id / HISTORY_FILE).as_posix()

def get_decisions_path(agent_dir: str, session_id: str)-> str:
    return (Path(get_sessions_dir(agent_dir)) / session_id / DECISIONS_FILE).as_posix()

def get_timeline_path(agent_dir: str, session_id: str)-> str:
        return (Path(get_sessions_dir(agent_dir)) / session_id / TIMELINE_FILE).as_posix()

def get_summary_path(agent_dir: str, session_id: str)-> str:
    return (Path(get_sessions_dir(agent_dir)) / session_id / SUMMARY_FILE).as_posix()

def _session_path(session_id: str) -> str:
    return (Path(SESSIONS_DIR) / f"{session_id}/current.jsonl").as_posix()

def format_date()->str:
    now = datetime.now()
    year = now.year
    month = str(now.month).zfill(2)
    day = str(now.day).zfill(2)
    return f"{year}-{month}-{day}"

def read_session_messages(sessions_dir: str, session_id: str)-> str:
    """L2: 读取完整对话（内部使用）"""
    session_dir: Path = Path(sessions_dir) / f"{session_id}"
    json_path: Path = session_dir / "current.jsonl"

    if not json_path.exists():
        return ""
    try:
        text_lines = json_path.read_text(encoding="utf-8").splitlines()
        messages = [json.loads(line.strip()) for line in text_lines if len(line) > 0]
        recent = messages[-MAX_MESSAGES_TO_READ:]
        return "\n\n".join([f"{r['role']}: {r['content']}" for r in recent])
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
# L1 解析：从 decisions 文本中提取时间戳 ID
# ========================
def extract_tsids(l1_text: str) -> List[str]:
    """
    从 L1 文本中提取所有时间戳 ID
    匹配格式: [202602260705]
    """
    ids: List[str] = []
    regex = re.compile(r'(\d{12})')

    for match in regex.finditer(l1_text):
        tsid = match.group(1)
        if tsid and tsid not in ids:
            ids.append(tsid)

    return ids

def add_tsid_to_l1(l1_text: List[str], tsid: str)-> str:
    """
    给 L1 的每条决策添加 [tsid] 前缀
    输入: "- 决策1\n- 决策2"
    输出: "- [202602260705] 决策1\n- [202602260705] 决策2"
    """
    tagged = []
    for line in l1_text:
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

def generate_tsid()->str:
    """
    生成时间戳 ID: YYYYMMDDHHmmss（如 202602260705）
    同时作为可读时间和唯一标识
    """
    now = datetime.now()
    year = now.year
    month = str(now.month).zfill(2)
    day = str(now.day).zfill(2)
    hour = str(now.hour).zfill(2)
    minute = str(now.minute).zfill(2)
    second = str(now.second).zfill(2)

    return f"{year}{month}{day}{hour}{minute}{second}"

async def append_timeline_entry(
    messages: List[BaseMessage],
    session_id: str,
    tool_metas: List[str],
)-> None:
    """
    写入：每轮结束后从 L2 生成 L0 + L1
    """
    try:
        tsid = generate_tsid()
        date_str = format_date()

        if not messages or len(messages) == 0:
            return

        tool_list = ", ".join(tool_metas) or "无"

        system = (
            "你是一个技术记录助手。根据完整对话内容，生成两部分输出。使用中文。\n\n"
            "严格按以下格式输出，不要输出任何其他内容：\n"
            "L0 是时间线目录，要极度精简，像书的章节标题。注意：只输出摘要文本本身，不要输出时间戳、不要输出\"- \"前缀，这些由系统自动添加。\n\n"
            "L1 是详细摘要，要包含具体的：\n"
            " - 技术方案（用了什么步骤、什么方法）\n"
            " - 程序配置类：文件路径、配置参数的具体值 其他类：具体材料、参数等\n"
            " - 程序配置类：代码改动（改了哪个文件、具体改了什么逻辑、为什么改） 其他类：做了什么 遵循什么逻辑 为什么这么做 等\n"
            " - 程序配置类：bug 根因和修复方式 其他类： 事件归因和解决方法\n"
            " - 确认的结论和共识\n\n"
            "L1 每条要有足够的细节，让人不看原文也能知道具体怎么做的。每条决策用 \"- \" 开头，一行一条。"
        )
        user = """===== 对话内容 =====
{messages_str}

===== 使用的工具 =====
{tool_list}

请按格式生成 [L0] 和 [L1]。"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system),
            ("human", user)
        ])

        summary: BaseModel = (prompt | summary_LLM.with_structured_output(Summary)).invoke(
            {"messages_str": "\n".join([f"**{m.type}**:{m.content}\n\n" for m in messages]), "tool_list": tool_list},
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
            timeline_path = get_timeline_path(ROOT_DIR, session_id)
            Path(timeline_path).parent.mkdir(parents=True, exist_ok=True)

            with open(timeline_path, "a", encoding="utf-8") as f:
                f.write(l0_line + "\n")

        # 写入 L1（每条决策添加 [tsid] 前缀）
        if summary.l1 is not None and len(summary.l1) > 0:
            l1_with_tsid = add_tsid_to_l1(summary.l1, tsid)
            decisions_path = get_decisions_path(ROOT_DIR, session_id)
            existing = safe_read_file(decisions_path).strip()

            today_header = f"## {date_str}"

            if today_header in existing:
                with open(decisions_path, "a", encoding="utf-8") as f:
                    f.write("\n" + l1_with_tsid + "\n")
            else:
                separator = "\n\n" if len(existing) > 0 else ""
                with open(decisions_path, "a", encoding="utf-8") as f:
                    f.write(separator + today_header + "\n" + l1_with_tsid)

    except Exception as e:
        print(e)

# ========================
# 读取 L0（始终加载）
# ========================
def load_l0_timeline(session_id: str) -> dict[str, Any]:
    """读取 L0（始终加载）"""
    timeline_path = get_timeline_path(ROOT_DIR, session_id)
    timeline = safe_read_file(timeline_path).strip()

    if not timeline:
        return {
            "available": False,
            "prompt": "",
            "raw_timeline": "",
            "recent_turns": DEFAULT_RECENT_TURNS,
        }

    prompt = f"<conversation_timeline>\n以下是历史对话的时间线索引：\n{timeline}\n </conversation_timeline>"

    return {
        "available": True,
        "prompt": prompt,
        "raw_timeline": timeline,
        "recent_turns": DEFAULT_RECENT_TURNS,
        "tsids": extract_tsids(timeline),
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

# ========================
# 读取 L1（按日期/时间戳ID 按需加载）
# ========================
def load_l1_decisions(
    # 会话 ID
    session_id: str,
    # 指定要加载的日期列表
    dates: Optional[List[str]] = None,
    # 指定要加载的时间戳 ID 列表（更精确的过滤）
    tsids: Optional[List[str]] = None,
)-> L1DecisionsResult:
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

    decisions_path = get_decisions_path(ROOT_DIR, session_id)
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


            tsid_match = re.search(r'\[(\d{14})\]', trimmed)
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
# L2: 按需加载（导出接口）
# ========================
def load_l2_session(session_id: str, tsids: List[str]) -> L2SessionResult:
    """
    按 sessionId 加载完整对话内容（L2）

    触发条件：Viking 路由判断 needsL2: true
    来源：从 L1/L0 提取时间戳 ID → 通过 tsidSessionMap 转换为 sessionId → 读取 JSONL
    """
    jsonl_path = Path(get_history_path(ROOT_DIR, session_id))
    if not tsids or len(tsids) == 0 or not jsonl_path.exists():
        return L2SessionResult(available=False, prompt="", loadedSessionIds=[])

    raw = jsonl_path.read_text(encoding="utf-8")
    lines = [json.loads(line) for line in raw.split("\n") if line.strip()]

    # 限制最大会话数
    target_ids = tsids[:L2_MAX_SESSIONS]

    session_text=""
    try:
        messages: List[dict] = []

        for line in lines:
            try:
                role = line.get("role")
                if role not in ("user", "assistant"):
                    continue

                content = line.get("content", "")
                if content.strip():
                    messages.append({
                        "role": role,
                        "content": content[:L2_MAX_CHARS_PER_MESSAGE]
                    })
            except:
                # skip invalid JSON lines
                pass

        # 只保留最近的消息
        recent = messages[-L2_MAX_MESSAGES_PER_SESSION:]
        session_text = "\n\n".join([f"[{m['role']}]: {m['content']}" for m in recent])

    except Exception as err:
        print(err)

    if len(session_text) == 0:
        ids_str = ", ".join(target_ids)
        print(f"[history] L2: no sessions loaded from [{ids_str}]")
        return L2SessionResult(available=False, prompt="", loadedSessionIds=[])

    prompt = f"<full_conversation>\n以下是相关的完整对话记录：\n\n{session_text}\n</full_conversation>"

    return L2SessionResult(
        available=True,
        prompt=prompt
    )

def load_summary(session_id: str) -> str:
    summary_path = get_summary_path(ROOT_DIR, session_id)
    if not Path(summary_path).exists():
        return ""

    return safe_read_file(summary_path)