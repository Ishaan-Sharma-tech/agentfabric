import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field

from agent_fabric.core.protocols import TeamStrategy
from agent_fabric.runtime.agent import Agent

logger = logging.getLogger("agent_fabric.runtime.team")

__all__ = [
    "TeamResult", 
    "AgentTool", 
    "SequentialStrategy", 
    "ParallelStrategy", 
    "SupervisorStrategy", 
    "Team"
]


class TeamResult(BaseModel):
    """Consolidated result returned by a Team run."""
    text: str
    outputs: Dict[str, Any] = Field(default_factory=dict)


class AgentTool:
    """Wrapper adapting an Agent into a Tool for Supervisor delegation."""
    def __init__(self, agent: Agent) -> None:
        self.agent = agent

    @property
    def name(self) -> str:
        return f"delegate_to_{self.agent.name}"

    @property
    def description(self) -> str:
        return f"Delegate a specific subtask to worker agent '{self.agent.name}'. Prompt: {self.agent.system_prompt}"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The exact task instruction to delegate to this worker agent."
                }
            },
            "required": ["task"]
        }

    async def execute(self, task: str, **kwargs) -> str:
        res = await self.agent.run(task)
        return res.text


class SequentialStrategy:
    """Executes agents sequentially, chaining each agent's output as context to the next."""
    async def execute(
        self, 
        task: str, 
        agents: List[Agent], 
        supervisor: Optional[Agent] = None, 
        **kwargs
    ) -> Dict[str, Any]:
        outputs: Dict[str, Any] = {}
        current_context = task
        
        for i, agent in enumerate(agents):
            if i == 0:
                prompt = current_context
            else:
                prompt = f"Previous step output:\n{current_context}\n\nNext Task Instructions:\n{task}"
                
            res = await agent.run(prompt)
            outputs[agent.name] = res.text
            current_context = res.text
            
        return {"text": current_context, "outputs": outputs}


class ParallelStrategy:
    """Executes all agents in parallel concurrently and combines their outputs."""
    async def execute(
        self, 
        task: str, 
        agents: List[Agent], 
        supervisor: Optional[Agent] = None, 
        **kwargs
    ) -> Dict[str, Any]:
        tasks = [agent.run(task) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        outputs: Dict[str, Any] = {}
        combined_snippets = []
        
        for agent, res in zip(agents, results):
            if isinstance(res, Exception):
                err_msg = f"Error executing agent '{agent.name}': {res}"
                outputs[agent.name] = err_msg
                combined_snippets.append(f"### Agent: {agent.name}\n{err_msg}")
            else:
                outputs[agent.name] = res.text
                combined_snippets.append(f"### Agent: {agent.name}\n{res.text}")
                
        combined_text = "\n\n".join(combined_snippets)
        return {"text": combined_text, "outputs": outputs}


class SupervisorStrategy:
    """Uses a supervisor agent equipped with worker agent tools to orchestrate and delegate tasks."""
    async def execute(
        self, 
        task: str, 
        agents: List[Agent], 
        supervisor: Optional[Agent] = None, 
        **kwargs
    ) -> Dict[str, Any]:
        worker_tools = [AgentTool(agent) for agent in agents]
        
        if supervisor is None:
            supervisor_agent = Agent(
                name="supervisor",
                system_prompt="You are a team supervisor. Analyze tasks and delegate work to your worker agent tools.",
                tools=worker_tools
            )
        else:
            supervisor_agent = supervisor
            supervisor_agent.tools.extend(worker_tools)
            
        res = await supervisor_agent.run(task)
        return {"text": res.text, "outputs": {"supervisor": res.text}}


class Team:
    """
    Multi-agent team manager orchestrating collaboration across multiple agents.
    """
    def __init__(
        self, 
        agents: List[Agent], 
        strategy: Union[str, TeamStrategy] = "sequential", 
        supervisor: Optional[Agent] = None,
        name: str = "team"
    ) -> None:
        self.name = name
        self.agents = agents
        self.supervisor = supervisor
        
        if isinstance(strategy, str):
            strat_lower = strategy.lower()
            if strat_lower == "sequential":
                self.strategy: TeamStrategy = SequentialStrategy()
            elif strat_lower == "parallel":
                self.strategy = ParallelStrategy()
            elif strat_lower == "supervisor":
                self.strategy = SupervisorStrategy()
            else:
                raise ValueError(f"Unknown team strategy: '{strategy}'")
        else:
            self.strategy = strategy

    async def run(self, task: str) -> TeamResult:
        """Execute the configured multi-agent team strategy on a task."""
        logger.info(f"Team '{self.name}' running task using {self.strategy.__class__.__name__}")
        raw_res = await self.strategy.execute(
            task=task, 
            agents=self.agents, 
            supervisor=self.supervisor
        )
        return TeamResult(text=raw_res["text"], outputs=raw_res.get("outputs", {}))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Team":
        """Instantiate a Team from a dictionary configuration."""
        name = data.get("name", "team")
        strategy = data.get("strategy", "sequential")
        
        raw_agents = data.get("agents", [])
        agents: List[Agent] = []
        for a in raw_agents:
            if isinstance(a, Agent):
                agents.append(a)
            elif isinstance(a, dict):
                agents.append(Agent.from_dict(a))
            elif isinstance(a, str):
                agents.append(Agent(name=a))
                
        supervisor = None
        if "supervisor" in data and data["supervisor"]:
            raw_sup = data["supervisor"]
            if isinstance(raw_sup, Agent):
                supervisor = raw_sup
            elif isinstance(raw_sup, dict):
                supervisor = Agent.from_dict(raw_sup)
            elif isinstance(raw_sup, str):
                supervisor = Agent(name=raw_sup)
                
        return cls(agents=agents, strategy=strategy, supervisor=supervisor, name=name)

    @classmethod
    def from_yaml(cls, path_or_content: Union[str, Path]) -> "Team":
        """Instantiate a Team from a YAML file path or raw YAML string."""
        import yaml
        content = str(path_or_content)
        p = Path(content)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML config for Team: {data}")
        return cls.from_dict(data)
