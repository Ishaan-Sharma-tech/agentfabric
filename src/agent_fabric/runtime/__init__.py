"""
AgentFabric runtime package.
Defines the Agent executor loop, multi-agent teams, Mailbox messaging, enhance() wrapper, and Runtime settings.
"""
from agent_fabric.runtime.runtime import Runtime as Runtime
from agent_fabric.runtime.agent import Agent as Agent, AgentResult as AgentResult
from agent_fabric.runtime.enhance import enhance as enhance, EnhancedAgentProxy as EnhancedAgentProxy
from agent_fabric.runtime.executor import run_in_background as run_in_background
from agent_fabric.runtime.mailbox import AgentMessage as AgentMessage, Mailbox as Mailbox
from agent_fabric.runtime.team import Team as Team, TeamResult as TeamResult, SequentialStrategy as SequentialStrategy, ParallelStrategy as ParallelStrategy, SupervisorStrategy as SupervisorStrategy

__all__ = [
    "Runtime",
    "Agent",
    "AgentResult",
    "enhance",
    "EnhancedAgentProxy",
    "run_in_background",
    "AgentMessage",
    "Mailbox",
    "Team",
    "TeamResult",
    "SequentialStrategy",
    "ParallelStrategy",
    "SupervisorStrategy",
]
