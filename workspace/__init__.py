"""Workspace package."""
CORE_FILE_NAMES = [
    "AGENTS.md",
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
]

ALL_FILE_NAMES = [
    *CORE_FILE_NAMES,
    "TOOLS.md",
    "HEARTBEAT.md",
    "SKILLS.md",
]

FILE_DESCRIPTIONS: dict[str, str] = {
  "AGENTS.md": "Agent核心规则：会话流程、安全、模块索引",
  "SOUL.md": "Agent人格、语气、性格（任何对话都需要）",
  "TOOLS.md": "本地环境备注（SSH、摄像头、TTS语音等）",
  "IDENTITY.md": "Agent身份：名字、emoji、头像（任何对话都需要）",
  "USER.md": "用户信息和偏好（个性化回复需要）",
  "HEARTBEAT.md": "心跳任务清单",
}