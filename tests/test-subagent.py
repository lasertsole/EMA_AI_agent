import time
import uuid
import asyncio
from pathlib import Path
from bus import MessageBus
from models import chat_model
from typing import Literal, Any
from workspace import CORE_FILE_NAMES
from logging import Logger, getLogger
from dataclasses import dataclass, field
from skills.loader import get_skills_text
from config import SRC_DIR, WORKSPACE_TEMPLATE_DIR, MEMORY_DIR
from tools import build_read_file_tool, build_write_file_tool, web_search_tool

logger: Logger = getLogger(__name__)

@dataclass(slots=True)
class SubagentStatus:
    """Real-time status of a running subagent."""

    task_id: str
    label: str
    task_description: str
    started_at: float          # time.monotonic()
    phase: Literal["initializing", "awaiting_tools", "tools_completed", "final_response", "done", "error"] \
        = "initializing"
    iteration: int = 0
    tool_events: list = field(default_factory=list)   # [{name, status, detail}, ...]
    usage: dict = field(default_factory=dict)          # token usage
    stop_reason: str | None = None
    error: str | None = None

class SubagentManager:
    """Manages background subagent execution."""

    def __init__(
        self,
        workspace: Path,
        max_tool_result_chars: int,
        bus: MessageBus | None = None,
        restrict_to_workspace: bool = False,
        disabled_skills: list[str] | None = None,
    ):
        self.workspace = workspace
        if bus is None:
            bus = MessageBus()
        self.bus = bus
        self.model = chat_model
        self.max_tool_result_chars = max_tool_result_chars
        self.restrict_to_workspace = restrict_to_workspace
        self.disabled_skills = set(disabled_skills or [])
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._task_statuses: dict[str, SubagentStatus] = {}
        self._session_tasks: dict[str, set[str]] = {}  # session_id -> {task_id, ...}

    async def spawn(
        self,
        session_id: str,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
    ) -> str:
        """Spawn a subagent to execute a task in the background."""
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        origin = {"channel": origin_channel, "chat_id": origin_chat_id}

        status = SubagentStatus(
            task_id=task_id,
            label=display_label,
            task_description=task,
            started_at=time.monotonic(),
        )
        self._task_statuses[task_id] = status

        bg_task = asyncio.create_task(
            self._run_subagent(task_id, task, display_label, origin, status)
        )
        self._running_tasks[task_id] = bg_task
        self._session_tasks.setdefault(session_id, set()).add(task_id)

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            self._task_statuses.pop(task_id, None)
            if ids := self._session_tasks.get(session_id):
                ids.discard(task_id)
                if not ids:
                    del self._session_tasks[session_id]

        bg_task.add_done_callback(_cleanup)

        logger.info("Spawned subagent [{}]: {}", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."

    @staticmethod
    def _build_subagent_prompt(task_prompt: str | None = None, selected_skill_names: list[str] | None = None) -> str:
        """
        创建子代理提示词

        Args:
            task_prompt: 任务提示词
            selected_skill_names: 选中skill的名称列表

        Returns:
            子代理提示词
        """

        skill_guide_text: str = f"""
        补充说明：
        1.将<skill_folder>替换成技能文件SKILL.md所在的目录 比如技能文件在 "./skills/text_to_image/SKILL.md", 那么文件目录就在 "./skills/text_to_image"
        2.技能生成的临时资源（如图片、语音等）存放在{(SRC_DIR / "image").as_posix()}目录下
        """
        skill_paths:str = get_skills_text(selected_skill_names = selected_skill_names, exclude_ext=True)
        skill_paths = f"{skill_paths}\n\n{skill_guide_text}"

        file_paths: list[str] = []

        # 确保一定有核心文件
        for f in CORE_FILE_NAMES:
            path = WORKSPACE_TEMPLATE_DIR / f
            if not path.exists():
                return ""
            file_paths.append(path.read_text(encoding="utf-8"))

        parts = [skill_paths, *file_paths, task_prompt]

        return "\n\n".join(p for p in parts if p)

    # async def _run_subagent(
    #     self,
    #     task_id: str,
    #     task: str,
    #     label: str,
    #     origin: dict[str, str],
    #     status: SubagentStatus,
    # ) -> None:
    #     """Execute the subagent task and announce the result."""
    #     logger.info("Subagent [{}] starting task: {}", task_id, label)
    #
    #     async def _on_checkpoint(payload: dict) -> None:
    #         status.phase = payload.get("phase", status.phase)
    #         status.iteration = payload.get("iteration", status.iteration)
    #
    #     try:
    #         # Build subagent tools (no message tool, no spawn tool)
    #         tools = [web_search_tool, build_read_file_tool(), build_write_file_tool()]
    #         system_prompt = self._build_subagent_prompt()
    #         messages: list[dict[str, Any]] = [
    #             {"role": "system", "content": system_prompt},
    #             {"role": "user", "content": task},
    #         ]
    #
    #         result = await self.runner.run(AgentRunSpec(
    #             initial_messages=messages,
    #             tools=tools,
    #             model=self.model,
    #             max_iterations=15,
    #             max_tool_result_chars=self.max_tool_result_chars,
    #             hook=_SubagentHook(task_id, status),
    #             max_iterations_message="Task completed but no final response was generated.",
    #             error_message=None,
    #             fail_on_tool_error=True,
    #             checkpoint_callback=_on_checkpoint,
    #         ))
    #         status.phase = "done"
    #         status.stop_reason = result.stop_reason
    #
    #         if result.stop_reason == "tool_error":
    #             status.tool_events = list(result.tool_events)
    #             await self._announce_result(
    #                 task_id, label, task,
    #                 self._format_partial_progress(result),
    #                 origin, "error",
    #             )
    #         elif result.stop_reason == "error":
    #             await self._announce_result(
    #                 task_id, label, task,
    #                 result.error or "Error: subagent execution failed.",
    #                 origin, "error",
    #             )
    #         else:
    #             final_result = result.final_content or "Task completed but no final response was generated."
    #             logger.info("Subagent [{}] completed successfully", task_id)
    #             await self._announce_result(task_id, label, task, final_result, origin, "ok")
    #
    #     except Exception as e:
    #         status.phase = "error"
    #         status.error = str(e)
    #         logger.error("Subagent [{}] failed: {}", task_id, e)
    #         await self._announce_result(task_id, label, task, f"Error: {e}", origin, "error")