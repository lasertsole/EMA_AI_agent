from typing import List, TypedDict, Optional


class ToolListIndexEntry(TypedDict):
    tools: List[str]
    description: str


"""构建工具包索引"""
TOOL_PACKS: dict[str, ToolListIndexEntry] = {}
def buildPackIndex()-> str:
    lines = [f"  - {name}: {pack['description']}" for name, pack in TOOL_PACKS.items()]

    return "\n".join(lines)

"""构建技能索引"""
class SkillIndexEntry(TypedDict):
    name: str
    description: str

def buildSkillIndex(skills: List[SkillIndexEntry])-> str:
    if len(skills) == 0:
        return "  (无)"

    lines = [f"  - ${s['name']}" for s in skills]
    return "\n".join(lines)

FILE_DESCRIPTIONS: dict[str, str]
def buildFileIndex(file_names: List[str])-> str:
    lines = [
        f"  - {name}: {FILE_DESCRIPTIONS.get(name, 'workspace文件')}"
            for name in file_names
    ]

    return "\n".join(lines)

class Prompt(TypedDict):
    system: str
    user: str

def buildRoutingPrompt(userMessage: str, fileNames: List[str], skills: List[SkillIndexEntry], timeline: Optional[str] = None)-> Prompt:
    SYSTEM: str = "You are a resource router. Select capability packs and files needed for the task. Reply with ONLY a JSON object, no other text, no markdown."
    PACK_INDEX: str = buildPackIndex()
    SKILL_INDEX: str = buildSkillIndex(skills)
    FILE_INDEX: str = buildFileIndex(fileNames)

    TIME_LINE_SECTION: str = (
        f"===== Conversation Timeline (L0) =====\n"
        f"This is a brief timeline of previous conversations. Each line has a date. "
        f"Use it to determine if the user is referencing past work, and which dates are relevant.\n"
        f"{timeline}"
        if timeline else ""
    )

    USER: str = (
        f"User message: {userMessage}\n"
        f"{TIME_LINE_SECTION}===== Capability Packs (select needed) =====\n"
        f"Always loaded: read + exec (do not select)\n"
        f"{PACK_INDEX}\n\n"
        f"===== Skills (for reference, all run via exec) =====\n"
        f"{SKILL_INDEX}\n\n"
        f"===== Workspace Files (select needed) =====\n"
        f"{FILE_INDEX}\n\n"
        "Reply JSON:\n"
        "{\"packs\":[\"pack names\"],\"files\":[\"file names\"],\"needsL1\":false,\"l1Dates\":[],\"needsL2\":false,\"reason\":\"brief reason\"}\n\n"
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

    return {"system": SYSTEM, "user": USER}

class RoutingModelResult(TypedDict):
    packs: List[str]
    files: List[str]
    needsL1: Optional[bool]
    l1Dates: Optional[List[str]]
    needsL2: Optional[bool]