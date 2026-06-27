import asyncio
import inspect
import functools
import logging
from typing import Any, Callable, Optional, Tuple
from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event
from agent_fabric.core.workspace import Workspace
from agent_fabric.memory.engine import memory_engine

logger = logging.getLogger("agent_fabric.runtime.enhance")

__all__ = ["EnhancedAgentProxy", "enhance"]


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
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        agent = object.__getattribute__(self, "_agent")
        attr = getattr(agent, name)
        if callable(attr) and not name.startswith("_"):
            return self._wrap_callable(name, attr)
        return attr

    def _wrap_callable(self, method_name: str, method: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap standard method calls with lifecycle hooks."""
        if inspect.iscoroutinefunction(method):
            @functools.wraps(method)
            async def async_wrapper(*args, **kwargs):
                task_input = self._extract_task_input(args, kwargs)
                
                modified_args, modified_kwargs = await self._async_before_hook(
                    task_input, args, kwargs
                )
                
                try:
                    result = await method(*modified_args, **modified_kwargs)
                except Exception as e:
                    await self._async_error_hook(task_input, e)
                    raise e
                
                await self._async_after_hook(task_input, result)
                return result
                
            return async_wrapper
        else:
            @functools.wraps(method)
            def sync_wrapper(*args, **kwargs):
                task_input = self._extract_task_input(args, kwargs)
                
                modified_args, modified_kwargs = self._sync_before_hook(
                    task_input, args, kwargs
                )
                
                try:
                    result = method(*modified_args, **modified_kwargs)
                except Exception as e:
                    self._sync_error_hook(task_input, e)
                    raise e
                
                self._sync_after_hook(task_input, result)
                return result
                
            return sync_wrapper

    def _extract_task_input(self, args: tuple, kwargs: dict) -> Optional[str]:
        """Heuristically extract the core task/prompt string from arguments."""
        for key in ("task", "query", "prompt", "message", "instruction"):
            if key in kwargs and isinstance(kwargs[key], str):
                return kwargs[key]
                
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
    
    async def _async_before_hook(self, task_input: Optional[str], args: tuple, kwargs: dict) -> Tuple[tuple, dict]:
        workspace = Workspace.current()
        new_kwargs = dict(kwargs)
        
        if self._observe_enabled:
            start_event = Event(
                event_type="AgentStarted",
                actor=f"enhanced:{self._name}",
                workspace=workspace.name,
                data={"task": task_input or "unknown"}
            )
            await event_bus.publish(start_event)
            
        if self._memory_enabled and task_input:
            memories = await memory_engine.search(task_input, limit=3)
            if memories:
                new_input = self._inject_context(task_input, memories)
                
                new_args = list(args)
                for i, arg in enumerate(args):
                    if isinstance(arg, str) and arg == task_input:
                        new_args[i] = new_input
                        return tuple(new_args), new_kwargs
                        
                for k, v in new_kwargs.items():
                    if isinstance(v, str) and v == task_input:
                        new_kwargs[k] = new_input
                        break
                        
        return args, new_kwargs

    async def _async_after_hook(self, task_input: Optional[str], result: Any) -> None:
        workspace = Workspace.current()
        
        if self._observe_enabled:
            stop_event = Event(
                event_type="AgentStopped",
                actor=f"enhanced:{self._name}",
                workspace=workspace.name,
                data={"result": str(result)}
            )
            await event_bus.publish(stop_event)
            
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

    # --- Synchronous Lifecycle Helpers ---

    def _run_coro_sync(self, coro: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=10)
        else:
            return asyncio.run(coro)

    def _sync_before_hook(self, task_input: Optional[str], args: tuple, kwargs: dict) -> Tuple[tuple, dict]:
        try:
            return self._run_coro_sync(self._async_before_hook(task_input, args, kwargs))
        except Exception as e:
            logger.warning(f"Error in sync before hook: {e}")
            return args, kwargs

    def _sync_after_hook(self, task_input: Optional[str], result: Any) -> None:
        try:
            self._run_coro_sync(self._async_after_hook(task_input, result))
        except Exception as e:
            logger.warning(f"Error in sync after hook: {e}")

    def _sync_error_hook(self, task_input: Optional[str], error: Exception) -> None:
        try:
            self._run_coro_sync(self._async_error_hook(task_input, error))
        except Exception as e:
            logger.warning(f"Error in sync error hook: {e}")


def enhance(
    agent_instance: Any, 
    memory: bool = True, 
    observe: bool = True
) -> Any:
    """
    Wrap any existing agent class instance with AgentFabric Memory and Observability hooks.
    """
    return EnhancedAgentProxy(agent_instance, memory_enabled=memory, observe_enabled=observe)

