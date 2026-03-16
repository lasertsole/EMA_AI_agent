"""Background task queue for compression and index updates."""

import asyncio
import logging
from typing import Any, Literal, List, Optional
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

logger = logging.getLogger(__name__)

TaskType = Literal["compress_session", "update_memory_index", "append_timeline_entry"]


class BackgroundTaskQueue:
    """Async task queue for background operations."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[TaskType, dict[str, Any]]] = asyncio.Queue()
        self._event_loop = asyncio.new_event_loop()

    def start(self) -> None:
        """Start the background worker."""
        if not self._event_loop.is_running():
            self._event_loop.call_soon(asyncio.create_task, self._worker())
            self._event_loop.run_forever()

    async def _worker(self) -> None:
        """Process tasks from the queue."""
        while True:
            task_type, data = await self.queue.get()
            try:
                match task_type:
                    case "compress_session":
                        # Import here to avoid circular dependency
                        from tasks.compress_sessions import compress_session
                        await compress_session(data["session_id"])

                    case "update_memory_index":
                        from tasks.memory_index import update_memory_index_incremental
                        await update_memory_index_incremental(data["new_content"])

                    case "append_timeline_entry":
                        from sessions.history_index import append_timeline_entry
                        await append_timeline_entry(messages=data["messages"], session_id=data["session_id"], tool_metas=data["tool_metas"])

                    case _:
                        logger.warning(f"Unknown task type: {task_type}")
            except Exception as e:
                logger.error(f"Task failed [{task_type}]: {e}", exc_info=True)
            finally:
                self.queue.task_done()

    def enqueue_compress(self, session_id: str) -> None:
        coro = self.queue.put(("compress_session", {"session_id": session_id}))
        asyncio.run_coroutine_threadsafe(coro, self._event_loop)

    def enqueue_memory_index(self, new_content: str) -> None:
        """Enqueue a memory index update task."""
        coro = self.queue.put(("update_memory_index", {"new_content": new_content}))
        asyncio.run_coroutine_threadsafe(coro, self._event_loop)

    def enqueue_append_timeline_entry(self, session_id: str, messages: List[BaseMessage], tool_metas:List[str] ) -> None:
        """Enqueue append timeline entry task."""
        coro = self.queue.put(("append_timeline_entry", {"session_id": session_id, "messages": messages, "tool_metas": tool_metas}))
        asyncio.run_coroutine_threadsafe(coro, self._event_loop)
