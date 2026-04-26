import time
import uuid
import asyncio
from bus import MessageBus
from agent import built_agent
from bus import InboundMessage
from typing import Literal, Any
from pydantic import BaseModel, Field
from workspace import CORE_FILE_NAMES
from logging import Logger, getLogger
from dataclasses import dataclass, field
from skills.loader import get_skills_text
from pub_func import render_template_file
from langgraph.graph.state import CompiledStateGraph
from config import SRC_DIR, WORKSPACE_DIR, SUBAGENT_TEMPLATE_DIR
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage


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
    tool_calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)          # token usage
    finish_reason: str | None = None
    error: str | None = None

class SubAgentOutput(BaseModel):
    """Output of a subagent task."""
    status: Literal["ok", "failed"] = Field(description="Whether the task was completed successfully or not (crash errors).", default="ok")
    finish_reason: str = Field(description="The reason why the task was finish, If the task failed due to tool errors, "
   "permission issues, or content policy violations, please explain the reasons in detail.", default="task completed")

class SubagentManager:
    """Manages background subagent execution."""

    """单例模式"""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        bus: MessageBus | None = None,
    ):
        if bus is None:
            bus = MessageBus()
        self._bus = bus
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._task_statuses: dict[str, SubagentStatus] = {}
        self._session_tasks: dict[str, set[str]] = {}  # session_id -> {task_id, ...}

        # 如果有运行中的事件循环，则使用它， 否则创建一个新的
        try:
            self._event_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._event_loop = asyncio.new_event_loop()

        SubagentManager._initialized = True

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

        bg_task = self._event_loop.create_task(
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

    def get_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop."""
        return self._event_loop
    
    def get_buts(self)-> MessageBus:
        return self._bus

    @staticmethod
    def _build_subagent_prompt(selected_skill_names: list[str] | None = None) -> str:
        """
        创建子代理提示词

        Args:
            selected_skill_names: 选中skill的名称列表

        Returns:
            子代理提示词
        """

        skill_guide_text: str = f"""
        补充说明：
        1.将<skill_folder>替换成技能文件SKILL.md所在的目录 比如技能文件在 "./skills/text_to_image/SKILL.md", 那么文件目录就在 "./skills/text_to_image"
        2.技能生成的临时资源（如图片、语音等）存放在{(SRC_DIR / "temp").as_posix()}目录下
        """
        skill_paths:str = get_skills_text(selected_skill_names = selected_skill_names, exclude_auth_skills=True) # 排除高权限技能
        skill_paths = f"{skill_paths}\n\n{skill_guide_text}"

        file_paths: list[str] = []

        # 确保一定有核心文件
        for core_file in CORE_FILE_NAMES:
            path = WORKSPACE_DIR / core_file
            if not path.exists():
                continue
            file_paths.append(path.read_text(encoding="utf-8"))

        parts = [skill_paths, *file_paths]

        return "\n\n".join(p for p in parts if p)

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        status: SubagentStatus,
    ) -> None:
        """Execute the subagent task and announce the result."""
        logger.info("Subagent [{}] starting task: {}", task_id, label)

        try:
            from context_engine import assemble

            # 复用主agent的 graph-memory，复用主模型经验以减少subagent试错成本
            assemble_result: dict[str, str] = await assemble(user_text=task, messages=[])
            graph_system_prompt_addition: str = assemble_result.get("system_prompt_addition", "")

            # 构建subagent系统提示词
            system_prompt = (
                self._build_subagent_prompt()
                + graph_system_prompt_addition
                + "\n\n Complete the task as simply as possible, and terminate immediately upon completion to submit the results.")
            messages: list[BaseMessage] = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=task),
            ]

            try:
                agent: CompiledStateGraph = built_agent(temperature = 0.5, response_format = SubAgentOutput)
                agent_res: dict[str, Any] = await agent.ainvoke(
                    input = {"messages": messages},
                    config = {"configurable": {"thread_id": 1}, "recursion_limit": 30}
                )
                structured_response: SubAgentOutput = agent_res.get("structured_response", {})

                status.phase = "done"
                status.finish_reason = structured_response.finish_reason

                announce_content: str = render_template_file(
                    file_path=(SUBAGENT_TEMPLATE_DIR / "subagent_announce.md").resolve().as_posix(),
                    variables={
                        "label": label,
                        "status_text": "completed successfully" if structured_response.status == "ok" else "failed",
                        "task": task,
                        "result": status.finish_reason,
                    }
                )
            except Exception as e:
                status.phase = "error"
                status.finish_reason = str(e)

                announce_content: str = render_template_file(
                    file_path=(SUBAGENT_TEMPLATE_DIR / "subagent_announce.md").resolve().as_posix(),
                    variables={
                        "label": label,
                        "status_text": "crash error",
                        "task": task,
                        "result": status.finish_reason,
                    }
                )

            override: str = origin.get("session_id") or f"{origin['channel']}:{origin['chat_id']}"
            msg = InboundMessage(
                channel = "system",
                sender_id = "subagent",
                chat_id = f"{origin['channel']}:{origin['chat_id']}",
                content = announce_content,
                session_id_override = override,
                metadata = {
                    "injected_event": "subagent_result",
                    "subagent_task_id": task_id,
                },
            )

            await self._bus.publish_inbound(msg)

        except Exception as e:
            status.phase = "error"
            status.error = str(e)
            logger.error("Subagent [{}] failed: {}", task_id, e)


    async def cancel_by_session(self, session_id: str) -> int:
        """Cancel all subagents for the given session. Returns count cancelled."""
        tasks = [self._running_tasks[tid] for tid in self._session_tasks.get(session_id, [])
                 if tid in self._running_tasks and not self._running_tasks[tid].done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    async def _inbound_consume_loop(self):
        while True:
            msg: InboundMessage = await self._bus.consume_inbound()

            print(msg)

    def start_service(self) -> None:
        if not self._event_loop.is_running():
            self._event_loop.create_task(self._inbound_consume_loop())

            # 防止重复运行报错
            try:
                self._event_loop.run_forever()
            except Exception:
                pass


    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)

    def get_running_count_by_session(self, session_id: str) -> int:
        """Return the number of currently running subagents for a session."""
        tids = self._session_tasks.get(session_id, set())
        return sum(
            1 for tid in tids
            if tid in self._running_tasks and not self._running_tasks[tid].done()
        )

subagent_manager = SubagentManager()