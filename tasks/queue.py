"""Background task queue for compression and index updates."""

import asyncio
import logging
from typing import Any, Literal
from threading import Thread, Lock

_logger = logging.getLogger(__name__)

TaskType = Literal["archive_session", "update_memory_index"]


class BackgroundTaskQueue:
    """Async task queue for background operations."""
    _instance = None
    _lock = Lock()  # tread safe lock

    def __new__(cls):
        """single instance"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)

                # ensure init process only invoke once
                cls._instance._initialized = False
        return cls._instance


    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self._queue: asyncio.Queue[tuple[TaskType, dict[str, Any]]] = asyncio.Queue()
        self._event_loop = asyncio.new_event_loop()

    def start(self) -> None:
        """Start the background worker."""
        if not self._event_loop.is_running():
            self._event_loop.call_soon(asyncio.create_task, self._worker())
            self._event_loop.run_forever()

    async def _worker(self) -> None:
        """Process tasks from the queue."""
        while True:
            task_type, data = await self._queue.get()
            try:
                match task_type:
                    case "archive_session":
                        # Import here to avoid circular dependency
                        from tasks.archive_sessions import archive_session
                        await archive_session(data["session_id"])

                    case "update_memory_index":
                        from tasks.memory_index import update_memory_index_incremental
                        await update_memory_index_incremental(data["new_content"])

                    case _:
                        _logger.warning(f"Unknown task type: {task_type}")
            except Exception as e:
                _logger.error(f"Task failed [{task_type}]: {e}", exc_info=True)
            finally:
                self._queue.task_done()

    def archive_compress(self, session_id: str) -> None:
        coro = self._queue.put(("archive_session", {"session_id": session_id}))
        asyncio.run_coroutine_threadsafe(coro, self._event_loop)

    def enqueue_memory_index(self, new_content: str) -> None:
        """Enqueue a memory index update task."""
        coro = self._queue.put(("update_memory_index", {"new_content": new_content}))
        asyncio.run_coroutine_threadsafe(coro, self._event_loop)

# 启动任务队列
task_queue: BackgroundTaskQueue = BackgroundTaskQueue()
_task_queue_thread: Thread = Thread(target=lambda: task_queue.start(), daemon=True)
_task_queue_thread.start()