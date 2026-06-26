import functools
import inspect
from typing import Callable, Any, Optional, Union, overload
from agent_fabric.core.protocols import ToolProtocol
from agent_fabric.tools.schema import generate_tool_schema
from agent_fabric.tools.registry import tool_registry


class FunctionTool:
    """
    Wraps a standard Python function and implements ToolProtocol.
    """
    def __init__(
        self, 
        func: Callable[..., Any], 
        description: Optional[str] = None, 
        name: Optional[str] = None
    ):
        self.func = func
        self._name = name or func.__name__
        self._description = description or func.__doc__ or f"Execute {self._name}"
        self._parameters = generate_tool_schema(func)
        functools.update_wrapper(self, func)

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict:
        return self._parameters

    async def execute(self, **kwargs) -> Any:
        """Execute the tool. Handles both sync and async wrapped functions."""
        if inspect.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        return self.func(**kwargs)

    def __call__(self, *args, **kwargs) -> Any:
        """Allow calling the wrapped function directly."""
        return self.func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"FunctionTool(name='{self.name}', description='{self.description[:40]}...')"


def tool(
    arg: Union[Callable[..., Any], str, None] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Any:
    """
    @tool decorator to convert standard Python functions into AgentFabric tools.
    Supports usage with or without arguments:
    
    @tool
    def search(query: str) -> str:
        '''Search the web.'''
        ...
        
    @tool(name="web_search", description="Search Google")
    def search(query: str) -> str:
        ...
    """
    if callable(arg):
        # Decorated directly: @tool
        ft = FunctionTool(arg)
        tool_registry.register(ft)
        return ft

    def decorator(func: Callable[..., Any]) -> FunctionTool:
        # Decorated with arguments: @tool(name="...", description="...")
        custom_name = name or (arg if isinstance(arg, str) else None)
        ft = FunctionTool(func, description=description, name=custom_name)
        tool_registry.register(ft)
        return ft

    return decorator
