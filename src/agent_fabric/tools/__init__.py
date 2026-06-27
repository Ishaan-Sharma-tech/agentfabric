"""
AgentFabric Tools system.
Provides a simple decorator to wrap Python functions into tools, auto-generates JSON Schema,
and executes tools within capability-based security boundaries.
"""
from agent_fabric.tools.decorator import tool as tool, FunctionTool as FunctionTool
from agent_fabric.tools.registry import tool_registry as tool_registry, ToolRegistry as ToolRegistry
from agent_fabric.tools.runtime import ToolExecutor as ToolExecutor
from agent_fabric.tools.schema import generate_tool_schema as generate_tool_schema

__all__ = [
    "tool",
    "FunctionTool",
    "tool_registry",
    "ToolRegistry",
    "ToolExecutor",
    "generate_tool_schema",
]
