"""
AgentFabric Tools system.
Provides a simple decorator to wrap Python functions into tools, auto-generates JSON Schema,
and executes tools within capability-based security boundaries.
"""
from agent_fabric.tools.decorator import tool
from agent_fabric.tools.registry import tool_registry
