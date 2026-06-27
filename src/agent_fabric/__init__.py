"""
AgentFabric: The runtime for AI agents.
"""
import asyncio
from typing import Any

__version__ = "0.1.0"

# Public SDK Facades
from agent_fabric.tools.decorator import tool as tool
from agent_fabric.tools.registry import tool_registry as tool_registry
from agent_fabric.memory.engine import memory_engine as memory, graph as graph
from agent_fabric.runtime.agent import Agent as Agent
from agent_fabric.runtime.team import Team as Team
from agent_fabric.runtime.enhance import enhance as enhance
from agent_fabric.runtime.runtime import Runtime as Runtime

__all__ = ["tool", "tool_registry", "memory", "graph", "Agent", "Team", "enhance", "Runtime", "run"]


def run(task: str, **kwargs) -> Any:
    """
    Zero-config package-level shortcut to run a task on a default Agent instance.
    If called within an active asyncio event loop, returns an awaitable coroutine.
    If called in a synchronous environment, blocks and returns the AgentResult directly.
    """
    agent = Agent(name="assistant", **kwargs)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        return agent.run(task)
    else:
        return asyncio.run(agent.run(task))
