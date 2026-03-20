"""
OpenViking 分层路由器
"""
import os
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from models import base_model
from tools import CORE_TOOLS, ALL_TOOLS
from typing import List, TypedDict, Optional
from langchain.messages import SystemMessage, HumanMessage
from workspace import CORE_FILE_NAMES, FILE_DESCRIPTIONS

current_dir = Path(__file__).parent.resolve()
env_path = current_dir / '.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
api_key = os.getenv("VIKING_API_KEY")
api_name = os.getenv("VIKING_API_NAME")
model_provider = os.getenv("VIKING_API_PROVIDER")

class RoutingModelResult(BaseModel):
    tools: List[str] = Field(description="List of capability tool names to load.")
    files: List[str] = Field(description="List of workspace files to load.")
    needs_l1: Optional[bool] = Field(description="Whether to load L1 layer index (historical key decisions). Set to true when user's question references previous work or requires context from past conversations")
    l1_dates: Optional[List[str]] = Field(description="List of dates for L1 decisions to load, Empty array means no specific L1 dates needed", examples=[[], ["2026-03-14"], ["2026-03-14", "2026-03-11"]])
    l1_tsids: Optional[List[str]] = Field(description="List of tsids for L1 decisions to load, Empty array means no specific L1 tsids needed", examples=[[], ["20260309232555"], ["20260309232745", "20260309232555"]])
    needs_l2: Optional[bool] = Field(description="Whether to load L2 layer full conversation history. Set to true when complete conversation context is required")

routing_model = base_model.bind(temperature=0)

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
  prompt_layer: PromptMode
  skipped: bool
  needs_l1: bool # 是否需要加载 L1 关键决策
  l1_dates: List[str] # 需要加载哪些日期的 L1 决策（空数组 = 不需要）
  l1_tsids: List[str] # 需要加载哪些具体时间的 L1 决策（空数组 = 不需要）
  needs_l2: bool # 是否需要加载 L2 完整对话

"""判断是否跳过路由"""
def should_skip_routing()-> bool:
  return not VIKING_ENABLED

class ToolListIndexEntry(TypedDict):
    tools: List[str]
    description: str

"""构建能力包索引"""
CORE_TOOL_NAMES: set[str] = set([ tool.name for tool in CORE_TOOLS])
def build_tool_index()-> str:
    lines = [f" - {tool.name}: {tool.description}" for tool in ALL_TOOLS]

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

def build_file_index(file_names: List[str])-> str:
    lines = [
        f"  - {name}: {FILE_DESCRIPTIONS.get(name, 'workspace文件')}"
            for name in file_names
    ]

    return "\n".join(lines)

class Prompt(TypedDict):
    system: str
    user: str

def build_routing_prompt(user_input: str, file_names: List[str], skills: List[SkillIndexEntry], timeline: Optional[str] = None)-> Prompt:
    system: str = "You are a resource router. Select capability tools and files needed for the task."
    tool_index: str = build_tool_index()
    skill_index: str = build_skill_index(skills)
    file_index: str = build_file_index(file_names)

    time_line_section: str = (
        f"===== Conversation Timeline (L0) =====\n"
        f"This is a brief timeline of previous conversations. Each line has a timestamp."
        f"Use it to determine if the user is referencing past work, and which dates are relevant.\n"
        f"{timeline}"
        if timeline else ""
    )

    user: str = (
        f"User message: {user_input}\n"
        f"{time_line_section}===== Capability Tools (select needed) =====\n"
        f"Always loaded: read + exec (do not select)\n"
        f"{tool_index}\n\n"
        f"===== Skills (for reference, all run via exec) =====\n"
        f"{skill_index}\n\n"
        f"===== Workspace Files (select needed) =====\n"
        f"{file_index}\n\n"

        "Rules:\n"
        "1. SKILLS: If the task matches any skill above, no extra tool needed (exec is always loaded). But if the skill also needs web/message/etc, include those tools.\n"
        "2. For ANY conversation: include SOUL.md, IDENTITY.md, USER.md.\n"
        "3. File editing/coding: include \"base-ext\".\n"
        "4. Simple chat: tools=[], files=[\"SOUL.md\",\"IDENTITY.md\",\"USER.md\"].\n"
        "5. When unsure: include more tools (cheap). Do NOT leave tools empty if the task needs"
    )

    return {"system": system, "user": user}


def call_routing_model(system: str, user: str)-> RoutingModelResult | None:
    messages = [
        SystemMessage(content = system),
        HumanMessage(content = user),
    ]
    
    try:
        return routing_model.invoke(messages).model_dump()
    except Exception as e:
        print(e)
        return None

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
    主入口
"""
def viking_route(
  user_input: str,
  tools: List[str],
  file_names: List[str],
  skills: List[SkillIndexEntry],
  timeline: Optional[str],  #L0 时间线原始文本，供路由模型判断是否需要 L1/L2
)-> VikingRouteResult:
    all_tool_names: set[str] = set(tools)
    all_file_names:set[str] = set(file_names)

    if should_skip_routing():
        return {
            "tools": all_tool_names,
            "files": all_file_names,
            "prompt_layer": PromptMode.FULL,
            "skipped": True,
            "needs_l1": False,
            "l1_dates": [],
            "l1_tsids": [],
            "needs_l2": False,
        }
                    
    if not user_input or len(user_input.strip()) == 0:
        return {
            "tools": set(CORE_TOOL_NAMES),
            "files": set(),
            "prompt_layer": PromptMode.L0,
            "skipped": False,
            "needs_l1": False,
            "l1_dates": [],
            "l1_tsids": [],
            "needs_l2": False,
        }

    routing_prompt = build_routing_prompt(user_input = user_input, file_names = file_names, skills = skills, timeline = timeline)
    result = call_routing_model(system = routing_prompt["system"], user = routing_prompt["user"])

    if result is None:
        return {
            "tools": all_tool_names,
            "files": all_file_names,
            "prompt_layer": PromptMode.FULL,
            "skipped": False,
            "needs_l1": False,
            "l1_dates": [],
            "l1_tsids": [],
            "needs_l2": False,
        }

    selected_tools:set[str] = set()

    # 如果模型选择了工具，则添加到路由工具列表里
    for t in result["tools"]:
        if t in all_tool_names:
            selected_tools.add(t)

    # 如果核心工具在已有工具的列表里，则总是加载核心工具
    for t in CORE_TOOL_NAMES:
        if t in all_tool_names:
            selected_tools.add(t)

    selected_files: set[str] = set()
    # 如果核心文件在已有文件的列表里，则总是加载核心文件
    for f in result["files"]:
        if f in all_file_names:
             selected_files.add(f)

    # 总是加载核心文件
    for f in CORE_FILE_NAMES:
         selected_files.add(f)

    # 根据工具数量选择路由层级
    tools_count:int = len(selected_tools)
    prompt_layer: PromptMode = (
       PromptMode.L0 if tools_count <= len(CORE_TOOL_NAMES) else
       PromptMode.L1 if tools_count <= len(ALL_TOOLS) else
       PromptMode.FULL
    )

    needs_l1:bool = result.get("needs_l1") if result.get("needs_l1") is not None else False
    l1_dates: List[str] = sorted(result.get("l1_dates"), reverse=True) if result.get("l1_dates") is not None else []
    l1_tsids: List[str] = sorted(result.get("l1_tsids"), reverse=True) if result.get("l1_tsids") is not None else []
    needs_l2: bool = result.get("needs_l2") if result.get("needs_l2") is not None else False

    return {
        "tools": selected_tools,
        "files": selected_files,
        "prompt_layer": prompt_layer,
        "skipped": False,
        "needs_l1": needs_l1,
        "l1_dates": l1_dates,
        "l1_tsids": l1_tsids,
        "needs_l2": needs_l2,
    }
