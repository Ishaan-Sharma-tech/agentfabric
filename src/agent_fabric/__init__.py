"""
AgentFabric: The runtime for AI agents.
"""

__version__ = "0.1.0"

from typing import Any

# Public SDK Facades
from agent_fabric.tools.decorator import tool
from agent_fabric.tools.registry import tool_registry
from agent_fabric.memory.engine import memory_engine as memory, graph
from agent_fabric.runtime.agent import Agent
from agent_fabric.runtime.enhance import enhance
from agent_fabric.runtime.runtime import Runtime

def run(task: str, **kwargs) -> Any:
    """
    Zero-config package-level shortcut to run a task on a temporary Agent.
    If executed in a running event loop, returns a coroutine to be awaited.
    Otherwise, blocks and executes synchronously, returning the AgentResult.
    """
    agent = Agent(name="assistant", **kwargs)
    
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        return agent.run(task)
    else:
        return asyncio.run(agent.run(task))



