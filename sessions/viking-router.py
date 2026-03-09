import os
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing import List, TypedDict, Optional, Literal, Any
from langchain.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

current_dir = Path(__file__).parent.resolve()
env_path = current_dir / '.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

class RoutingModelResult(BaseModel):
    packs: List[str] = Field(description="List of capability pack names to load.")
    files: List[str] = Field(description="List of workspace files to load.")
    needsL1: Optional[bool] = Field(description="Whether to load L1 layer index (historical key decisions). Set to true when user's question references previous work or requires context from past conversations")
    l1Dates: Optional[List[str]] = Field(description="List of dates for L1 decisions to load, format: ['YYYY-MM-DD']. Empty array means no specific L1 dates needed")
    needsL2: Optional[bool] = Field(description="Whether to load L2 layer full conversation history. Set to true when complete conversation context is required")

routing_model = init_chat_model(
    model_provider = model_provider,
    model = api_name,
    api_key = api_key,
    temperature = 0,
    max_retries = 2,
).with_structured_output(RoutingModelResult)

"""
Controls which hardcoded sections are included in the system prompt.
"full": All sections (default, for main agent)
"L1": Standard sections (Tooling, Safety, Memory, Workspace, Skills, Runtime)
    skips: CLI Reference, Self-Update, Messaging, Heartbeats, Silent Replies,
    Model Aliases, Sandbox, Voice, Reply Tags, Reactions
"L0": Minimal chat sections (Safety, Workspace, Runtime, Project Context only)
    skips everything L1 skips plus: Tooling, Tool Call Style, Skills, Memory, Docs
"minimal": Reduced sections (Tooling, Workspace, Runtime) - used for subagents
"none": Just basic identity line, no sections
"""
class PromptMode(Enum):
    FULL = "full"
    L1 = "L1"
    L0 = "L0"
    MINIMAL = "minimal"
    NONE = "none"

"""总开关"""
VIKING_ENABLED:bool = True

"""类型"""
class VikingRouteResult(TypedDict):
  tools: set[str]
  files: set[str]
  promptLayer: PromptMode
  skillsMode: Literal["names", "summaries"]
  skipped: bool
  needsL1: bool # 是否需要加载 L1 关键决策
  l1Dates: List[str] # 需要加载哪些日期的 L1 决策（空数组 = 不需要）
  needsL2: bool # 是否需要加载 L2 完整对话

"""判断是否跳过路由"""
def should_skip_routing()-> bool:
  return not VIKING_ENABLED

class ToolListIndexEntry(TypedDict):
    tools: List[str]
    description: str

"""构建能力包索引"""
CORE_TOOLS: set[str] = {"read", "exec"}
TOOL_PACKS: dict[str, ToolListIndexEntry] = {
    "base-ext": {
        "tools": ["write", "edit", "apply_patch", "grep", "find", "ls", "process"],
        "description": "文件编辑、搜索、目录操作、后台进程管理",
    },
    "web": {
        "tools": ["web_search", "web_fetch"],
        "description": "搜索互联网、抓取网页内容",
    },
    "browser": {
        "tools": ["browser"],
        "description": "控制浏览器打开和操作网页",
    },
    "message": {
        "tools": ["message"],
        "description": "发送消息到钉钉、Telegram、Discord等通道",
    },
    "media": {
        "tools": ["canvas", "image"],
        "description": "图片生成、画布展示和截图",
    },
    "infra": {
        "tools": ["cron", "gateway", "session_status"],
        "description": "定时任务、系统管理、状态查询、提醒",
    },
    "agents": {
        "tools": ["agents_list", "sessions_list", "sessions_history", "sessions_send", "sessions_spawn", "subagents"],
        "description": "多Agent协作、子任务派发、会话管理",
    },
    "nodes": {
        "tools": ["nodes"],
        "description": "设备控制、摄像头、屏幕操作",
    },
}
def build_pack_index()-> str:
    lines = [f"  - {name}: {pack['description']}" for name, pack in TOOL_PACKS.items()]

    return "\n".join(lines)

"""构建技能索引"""
class SkillIndexEntry(TypedDict):
    name: str
    description: str

def build_skill_index(skills: List[SkillIndexEntry])-> str:
    if len(skills) == 0:
        return "  (无)"

    lines = [f"  - ${s['name']}" for s in skills]
    return "\n".join(lines)

FILE_DESCRIPTIONS: dict[str, str] = {
  "AGENTS.md": "Agent核心规则：会话流程、安全、模块索引",
  "SOUL.md": "Agent人格、语气、性格（任何对话都需要）",
  "TOOLS.md": "本地环境备注（SSH、摄像头、TTS语音等）",
  "IDENTITY.md": "Agent身份：名字、emoji、头像（任何对话都需要）",
  "USER.md": "用户信息和偏好（个性化回复需要）",
  "HEARTBEAT.md": "心跳任务清单",
  "BOOTSTRAP.md": "首次运行引导（仅首次需要）",
}
def build_file_index(file_names: List[str])-> str:
    lines = [
        f"  - {name}: {FILE_DESCRIPTIONS.get(name, 'workspace文件')}"
            for name in file_names
    ]

    return "\n".join(lines)

class Prompt(TypedDict):
    system: str
    user: str

def build_routing_prompt(user_message: str, file_names: List[str], skills: List[SkillIndexEntry], timeline: Optional[str] = None)-> Prompt:
    system: str = "You are a resource router. Select capability packs and files needed for the task."
    pack_index: str = build_pack_index()
    skill_index: str = build_skill_index(skills)
    file_index: str = build_file_index(file_names)

    time_line_section: str = (
        f"===== Conversation Timeline (L0) =====\n"
        f"This is a brief timeline of previous conversations. Each line has a date. "
        f"Use it to determine if the user is referencing past work, and which dates are relevant.\n"
        f"{timeline}"
        if timeline else ""
    )

    user: str = (
        f"User message: {user_message}\n"
        f"{time_line_section}===== Capability Packs (select needed) =====\n"
        f"Always loaded: read + exec (do not select)\n"
        f"{pack_index}\n\n"
        f"===== Skills (for reference, all run via exec) =====\n"
        f"{skill_index}\n\n"
        f"===== Workspace Files (select needed) =====\n"
        f"{file_index}\n\n"

        "Rules:\n"
        "1. SKILLS: If the task matches any skill above, no extra pack needed (exec is always loaded). But if the skill also needs web/message/etc, include those packs.\n"
        "2. For ANY conversation: include SOUL.md, IDENTITY.md, USER.md.\n"
        "3. File editing/coding: include \"base-ext\".\n"
        "4. Web search: include \"web\".\n"
        "5. Send messages/notifications: include \"message\".\n"
        "6. Scheduled tasks/reminders: include \"infra\".\n"
        "7. Simple chat: packs=[], files=[\"SOUL.md\",\"IDENTITY.md\",\"USER.md\"].\n"
        "8. When unsure: include more packs (cheap). Do NOT leave packs empty if the task needs"
    )

    return {"system": system, "user": user}


def call_routing_model(system: str, user: str)-> dict[str, Any] | None:
    messages = [
        SystemMessage(content = system),
        HumanMessage(content = user),
    ]
    
    try:
        return routing_model.invoke(messages, max_tokens = 200).model_dump()
    except Exception as e:
        print(e)
        return None

"""
    展开能力包
"""
def expand_packs(pack_names: List[str])->set[str]:
    tools = CORE_TOOLS
    for name in pack_names:
        pack = TOOL_PACKS[name]
        if pack:
            for tool in pack["tools"]:
                tools.add(tool)
        else:
            print(f"[viking] unknown pack \"{name}\", ignored")

    return tools

"""
    Skills 名称+描述列表
"""
def build_skill_names_only_prompt(skills: List[SkillIndexEntry])-> str:
  if len(skills) == 0:
      return ""

  lines = [
      f"- {s['name']}: {s['description']}" if s['description'] else f"- {s['name']}"
      for s in skills
  ]

  return "\n".join([
      "## Skills",
      *lines,
      "Use `read` on the skill's SKILL.md when needed.",
  ])

"""
    TODO 主入口
"""
class AgentToolLike(TypedDict):
  name: str
  description: Optional[str]

async def viking_route(
  prompt: str,
  tools: List[AgentToolLike],
  file_names: List[str],
  skills: List[SkillIndexEntry],
  timeline: Optional[str],  #L0 时间线原始文本，供路由模型判断是否需要 L1/L2
)-> VikingRouteResult:
    all_tool_names:set[str] = set([t["name"] for t in tools])
    all_file_names:set[str] = set(file_names)
    
    if should_skip_routing():
        return {
            "tools": all_tool_names,
            "files": all_file_names,
            "promptLayer": PromptMode.FULL,
            "skillsMode": "summaries",
            "skipped": True,
            "needsL1": False,
            "l1Dates": [],
            "needsL2": False,
        }
                    
    if not prompt or len(prompt.strip()) == 0:
        return {
            "tools": set(CORE_TOOLS),
            "files": set(),
            "promptLayer": PromptMode.L0,
            "skillsMode": "names",
            "skipped": False,
            "needsL1": False,
            "l1Dates": [],
            "needsL2": False,
        }

    routing_prompt = build_routing_prompt(user_message= prompt, file_names= file_names, skills= skills, timeline= timeline)
    result = call_routing_model(system = routing_prompt["system"], user = routing_prompt["user"])

    if result is None:
        return {
            "tools": all_tool_names,
            "files": all_file_names,
            "promptLayer": PromptMode.FULL,
            "skillsMode": "summaries",
            "skipped": False,
            "needsL1": False,
            "l1Dates": [],
            "needsL2": False,
        }

    expanded_tools:set[str] = expand_packs(result["packs"])

    valid_tools:set[str] = set()
    for t in expanded_tools:
        if t in all_file_names:
            valid_tools.add(t)
            
    for c in CORE_TOOLS:
        if c in all_file_names:
            valid_tools.add(c)
    
    selected_files:set[str] = set(result["files"]) & all_file_names
    count:int = len(valid_tools)
    
    prompt_layer: PromptMode = (
       PromptMode.L0 if count <= 2 else
       PromptMode.L1 if count <= 12 else
       PromptMode.FULL
    )
    
    needs_l1:bool = result.get("needsL1") if result.get("needsL1") is not None else False
    l1_dates: List[str] = result.get("l1Dates") if result.get("l1Dates") is not None else []
    needs_l2: bool = result.get("needsL2") if result.get("needsL2") is not None else False
    return {
       "tools": valid_tools,
       "files": selected_files,
       "promptLayer": prompt_layer,
       "skillsMode": "names",
       "skipped": False,
       "needsL1": needs_l1,
       "l1Dates": l1_dates,
       "needsL2": needs_l2,
    }
