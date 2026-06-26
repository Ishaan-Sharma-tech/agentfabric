import asyncio
import inspect
import functools
import logging
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone
from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event
from agent_fabric.core.workspace import Workspace
from agent_fabric.memory.engine import memory_engine

logger = logging.getLogger("agent_fabric.runtime.enhance")


class EnhancedAgentProxy:
    """
    Proxy wrapper that intercepts calls to an existing agent's methods,
    injecting AgentFabric Memory and Observability capabilities.
    """
    def __init__(
        self, 
        agent_instance: Any, 
        memory_enabled: bool = True, 
        observe_enabled: bool = True
    ) -> None:
        self._agent = agent_instance
        self._memory_enabled = memory_enabled
        self._observe_enabled = observe_enabled
        self._name = agent_instance.__class__.__name__

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._agent, name)
        if callable(attr) and not name.startswith("_"):
            return self._wrap_callable(name, attr)
        return attr

    def _wrap_callable(self, method_name: str, method: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap standard method calls with lifecycle hooks."""
        
        # Check if the target method is async
        if inspect.iscoroutinefunction(method):
            @functools.wraps(method)
            async def async_wrapper(*args, **kwargs):
                task_input = self._extract_task_input(args, kwargs)
                
                # 1. Before Hooks (Memory search, Event emit)
                modified_args, modified_kwargs = await self._async_before_hook(
                    task_input, args, kwargs
                )
                
                # 2. Method Execution
                try:
                    result = await method(*modified_args, **modified_kwargs)
                except Exception as e:
                    await self._async_error_hook(task_input, e)
                    raise e
                
                # 3. After Hooks (Memory store, Event emit)
                await self._async_after_hook(task_input, result)
                return result
                
            return async_wrapper
        else:
            @functools.wraps(method)
            def sync_wrapper(*args, **kwargs):
                task_input = self._extract_task_input(args, kwargs)
                
                # 1. Before Hooks (Synchronous helper)
                modified_args, modified_kwargs = self._sync_before_hook(
                    task_input, args, kwargs
                )
                
                # 2. Method Execution
                try:
                    result = method(*modified_args, **modified_kwargs)
                except Exception as e:
                    self._sync_error_hook(task_input, e)
                    raise e
                
                # 3. After Hooks (Synchronous helper)
                self._sync_after_hook(task_input, result)
                return result
                
            return sync_wrapper

    def _extract_task_input(self, args: tuple, kwargs: dict) -> Optional[str]:
        """Heuristically extract the core task/prompt string from arguments."""
        # 1. Look for 'task', 'query', or 'prompt' keys in kwargs
        for key in ("task", "query", "prompt", "message", "instruction"):
            if key in kwargs and isinstance(kwargs[key], str):
                return kwargs[key]
                
        # 2. Fall back to the first string argument in positional args
        for arg in args:
            if isinstance(arg, str):
                return arg
                
        return None

    def _inject_context(self, task_input: str, memories: list) -> str:
        """Inject context memory directly into the task string."""
        if not memories:
            return task_input
            
        context_snippet = "\n".join([f"- {m.text}" for m in memories])
        return (
            f"[CONTEXT MEMORY] Here is relevant context retrieved from AgentFabric store:\n"
            f"{context_snippet}\n\n"
            f"Original Input: {task_input}"
        )

    # --- Async Lifecycle Hooks ---
    
    async def _async_before_hook(self, task_input: Optional[str], args: tuple, kwargs: dict) -> tuple:
        workspace = Workspace.current()
        
        # Publish AgentStarted Event
        if self._observe_enabled:
            start_event = Event(
                event_type="AgentStarted",
                actor=f"enhanced:{self._name}",
                workspace=workspace.name,
                data={"task": task_input or "unknown"}
            )
            await event_bus.publish(start_event)
            
        # Retrieve context memory
        if self._memory_enabled and task_input:
            memories = await memory_engine.search(task_input, limit=3)
            if memories:
                # Prepend context to the string parameter
                new_input = self._inject_context(task_input, memories)
                
                # Reconstruct arguments
                # Positional override
                new_args = list(args)
                for i, arg in enumerate(args):
                    if isinstance(arg, str) and arg == task_input:
                        new_args[i] = new_input
                        return tuple(new_args), kwargs
                        
                # Kwargs override
                for k, v in kwargs.items():
                    if isinstance(v, str) and v == task_input:
                        kwargs[k] = new_input
                        break
                        
        return args, kwargs

    async def _async_after_hook(self, task_input: Optional[str], result: Any) -> None:
        workspace = Workspace.current()
        
        # Publish AgentStopped Event
        if self._observe_enabled:
            stop_event = Event(
                event_type="AgentStopped",
                actor=f"enhanced:{self._name}",
                workspace=workspace.name,
                data={"result": str(result)}
            )
            await event_bus.publish(stop_event)
            
        # Save run to Memory Engine
        if self._memory_enabled and task_input:
            summary = f"Task: {task_input}\nResult: {result}"
            await memory_engine.store(
                text=summary,
                tags=["enhanced_run", self._name],
                agent_id=self._name
            )

    async def _async_error_hook(self, task_input: Optional[str], error: Exception) -> None:
        workspace = Workspace.current()
        if self._observe_enabled:
            error_event = Event(
                event_type="AgentFailed",
                actor=f"enhanced:{self._name}",
                workspace=workspace.name,
                data={"task": task_input or "unknown", "error": str(error)}
            )
            await event_bus.publish(error_event)

    # --- Synchronous Lifecycle Hooks (Runs async event loop methods in blocking calls) ---

    def _sync_before_hook(self, task_input: Optional[str], args: tuple, kwargs: dict) -> tuple:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            # If running in another event loop, we can't block. Just do a quick task creation
            loop.create_task(self._async_before_hook(task_input, args, kwargs))
            return args, kwargs
        else:
            return loop.run_until_complete(self._async_before_hook(task_input, args, kwargs))

    def _sync_after_hook(self, task_input: Optional[str], result: Any) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            loop.create_task(self._async_after_hook(task_input, result))
        else:
            loop.run_until_complete(self._async_after_hook(task_input, result))

    def _sync_error_hook(self, task_input: Optional[str], error: Exception) -> None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            loop.create_task(self._async_error_hook(task_input, error))
        else:
            loop.run_until_complete(self._async_error_hook(task_input, error))


def enhance(
    agent_instance: Any, 
    memory: bool = True, 
    observe: bool = True
) -> Any:
    """
    Wrap any existing agent class instance with AgentFabric Memory and Observability hooks.
    Works for both sync and async method runners.
    """
    return EnhancedAgentProxy(agent_instance, memory_enabled=memory, observe_enabled=observe)
