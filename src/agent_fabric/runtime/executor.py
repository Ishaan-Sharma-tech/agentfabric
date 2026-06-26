import asyncio
from typing import Coroutine, Any


def run_in_background(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """
    Schedules an async coroutine to execute concurrently in the active event loop.
    Returns the created asyncio.Task object.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Fallback if no loop is running (starts a new one or raises)
        raise RuntimeError("No running asyncio event loop found. Ensure you are running inside an async context.")
        
    return loop.create_task(coro)
