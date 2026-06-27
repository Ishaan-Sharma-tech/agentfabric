import asyncio
import logging
from typing import Coroutine, Any

logger = logging.getLogger("agent_fabric.runtime.executor")

__all__ = ["run_in_background"]


def run_in_background(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """
    Schedules an async coroutine to execute concurrently in the active event loop.
    Returns the created asyncio.Task object with error handling callbacks attached.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        raise RuntimeError("No running asyncio event loop found. Ensure you are running inside an async context.")
        
    task = loop.create_task(coro)
    
    def _on_done(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception():
            exc = t.exception()
            logger.error(f"Background task '{t.get_name()}' failed with exception: {exc}", exc_info=exc)
            
    task.add_done_callback(_on_done)
    return task

