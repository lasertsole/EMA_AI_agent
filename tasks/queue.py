"""Background task queue for compression and index updates."""

import asyncio
import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

TaskType = Literal["compress_session", "update_memory_index"]


class BackgroundTaskQueue:
    """Async task queue for background operations."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[TaskType, dict[str, Any]]] = asyncio.Queue()
        self.worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background worker."""
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("Background task queue started")

    async def stop(self) -> None:
        """Stop the background worker gracefully."""
        if self.worker_task:
            # Wait for queue to drain first
            try:
                await asyncio.wait_for(self.queue.join(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Queue did not drain within timeout")

            # Then cancel worker
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        logger.info("Background task queue stopped")

    async def _worker(self) -> None:
        """Process tasks from the queue."""
        while True:
            task_type, data = await self.queue.get()
            try:
                if task_type == "compress_session":
                    # Import here to avoid circular dependency
                    from tasks.compress import compress_session
                    await compress_session(data["session_id"])
                elif task_type == "update_memory_index":
                    from tasks.memory_index import update_memory_index_incremental
                    await update_memory_index_incremental(data["new_content"])
                else:
                    logger.warning(f"Unknown task type: {task_type}")
            except Exception as e:
                logger.error(f"Task failed [{task_type}]: {e}", exc_info=True)
            finally:
                self.queue.task_done()

    async def enqueue_compress(self, session_id: str) -> None:
        """Enqueue a session compression task."""
        await self.queue.put(("compress_session", {"session_id": session_id}))

    async def enqueue_memory_index(self, new_content: str) -> None:
        """Enqueue a memory index update task."""
        await self.queue.put(("update_memory_index", {"new_content": new_content}))
