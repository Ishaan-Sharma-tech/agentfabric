import re
import json
import logging
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

from agent_fabric.core.config import settings
from agent_fabric.core.models import Event
from agent_fabric.core.permissions import Capability, DEVELOPER_CAPABILITIES
from agent_fabric.core.events import event_bus
from agent_fabric.core.workspace import Workspace
from agent_fabric.memory.engine import memory_engine
from agent_fabric.tools.registry import tool_registry
from agent_fabric.tools.runtime import ToolExecutor
from agent_fabric.providers.openai import OpenAIProvider
from agent_fabric.providers.ollama import OllamaProvider
from agent_fabric.providers.anthropic import AnthropicProvider
from agent_fabric.providers.google import GoogleGeminiProvider
from agent_fabric.providers.groq_provider import GroqProvider
from agent_fabric.providers.lmstudio import LMStudioProvider
from agent_fabric.observability.logger import setup_agent_logger

logger = logging.getLogger("agent_fabric.runtime.agent")

__all__ = ["AgentResult", "Agent"]

AGENT_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def validate_agent_name(name: str) -> str:
    if not AGENT_NAME_RE.match(name):
        raise ValueError(
            f"Invalid agent name '{name}'. Must be 1-64 alphanumeric characters, "
            "dashes, underscores, or dots, and start with an alphanumeric character."
        )
    return name


class AgentResult(BaseModel):
    """Execution output from an Agent run."""
    text: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    raw_response: Optional[Any] = None


class Agent:
    """
    Core Agent class — managing LLM chat interactions, tool execution,
    isolated execution history, and memory persistence.
    """
    def __init__(
        self,
        name: str = "assistant",
        model: Optional[str] = None,
        tools: Optional[List[Union[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        provider: Optional[Union[str, Any]] = None,
        capabilities: Optional[List[Capability]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> None:
        self.name = validate_agent_name(name)
        self.system_prompt = system_prompt or f"You are a helpful AI assistant named {name}."
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Isolated agent logger setup
        self.logger = setup_agent_logger(self.name)
        
        # Capability checks default to DEVELOPER_CAPABILITIES
        self.capabilities = capabilities or DEVELOPER_CAPABILITIES
        
        # Resolve LLM Provider
        provider_name = provider or settings.default_provider
        if isinstance(provider_name, str):
            p_lower = provider_name.lower()
            if p_lower == "openai":
                self.provider = OpenAIProvider(default_model=model)
            elif p_lower == "ollama":
                self.provider = OllamaProvider(default_model=model)
            elif p_lower == "anthropic":
                self.provider = AnthropicProvider(default_model=model)
            elif p_lower in ("google", "gemini"):
                self.provider = GoogleGeminiProvider(default_model=model)
            elif p_lower == "groq":
                self.provider = GroqProvider(default_model=model)
            elif p_lower == "lmstudio":
                self.provider = LMStudioProvider(default_model=model)
            else:
                raise ValueError(f"Unsupported built-in provider: {provider_name}")
        else:
            self.provider = provider_name
            
        # Resolve and load tools
        self.tools = []
        for t in (tools or []):
            if isinstance(t, str):
                tool_instance = tool_registry.get(t)
                if tool_instance:
                    self.tools.append(tool_instance)
                else:
                    self.logger.warning(f"Tool '{t}' was not found in the registry and will be skipped.")
            else:
                self.tools.append(t)
                
        # Initialize conversation messages history
        self.messages: List[Dict[str, Any]] = []
        self._reset_history()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Agent":
        """Instantiate an Agent from a dictionary profile configuration."""
        name = data.get("name") or data.get("agent_name") or "agent"
        return cls(
            name=name,
            model=data.get("model"),
            tools=data.get("tools"),
            system_prompt=data.get("system_prompt") or data.get("system"),
            provider=data.get("provider"),
            capabilities=data.get("capabilities"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens")
        )

    @classmethod
    def from_yaml(cls, path_or_content: Union[str, Any]) -> "Agent":
        """Instantiate an Agent from a YAML file path or raw YAML string."""
        import yaml
        from pathlib import Path
        content = str(path_or_content)
        p = Path(content)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML config for Agent: {data}")
        return cls.from_dict(data)

    def _reset_history(self) -> None:
        """Reset conversation history with system prompt."""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def logs(self) -> List[Dict[str, Any]]:
        """Retrieve execution log statements for this agent."""
        workspace = Workspace.current()
        log_file = workspace.logs_path / f"{self.name}.log"
        if not log_file.exists():
            return []
        
        logs = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except Exception:
                    pass
        return logs

    async def run(self, task: str, max_steps: int = 10) -> AgentResult:
        """
        Execute a task. Queries memory for context, executes the agent loop,
        runs tool calling iterations, and persists results to the memory engine.
        """
        # Reset history on every run to avoid memory context leaks
        self._reset_history()
        
        workspace = Workspace.current()
        self.logger.info(f"Starting execution run for task: '{task}'")
        
        # Publish AgentStarted Event
        model_name = getattr(self.provider, "default_model", "unknown")
        if not isinstance(model_name, str):
            model_name = str(model_name)
            
        start_event = Event(
            event_type="AgentStarted",
            actor=f"agent:{self.name}",
            workspace=workspace.name,
            data={"task": task, "model": model_name}
        )
        await event_bus.publish(start_event)

        # 1. Retrieve Context from Memory Engine
        try:
            memories = await memory_engine.search(task, limit=3)
            if memories:
                context_snippet = "\n".join([f"- {m.text}" for m in memories])
                system_injection = (
                    f"\n\n[CONTEXT MEMORY] Here is relevant context retrieved from your memory store:\n"
                    f"{context_snippet}"
                )
                for msg in self.messages:
                    if msg["role"] == "system":
                        msg["content"] += system_injection
                        break
        except Exception as e:
            self.logger.warning(f"Failed to retrieve context memory: {e}")

        # 2. Append User Task to message history
        self.messages.append({"role": "user", "content": task})

        # 3. Agent Execution Loop with try/finally exception safety
        tool_executor = ToolExecutor(self.name, self.capabilities)
        step = 0
        final_text = ""
        
        try:
            while step < max_steps:
                step += 1
                self.logger.info(f"Agent execution loop step {step}/{max_steps}")
                
                response = await self.provider.chat(
                    messages=self.messages,
                    tools=self.tools,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                raw_content = response.get("content") or ""
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": raw_content
                }
                if response.get("tool_calls"):
                    assistant_msg["tool_calls"] = response["tool_calls"]
                self.messages.append(assistant_msg)
                
                final_text = raw_content
                tool_calls = response.get("tool_calls", [])
                
                if not tool_calls:
                    self.logger.info("Agent loop finished executing.")
                    break
                    
                for tc in tool_calls:
                    call_id = tc["id"]
                    tool_name = tc["name"]
                    arguments = tc["arguments"]
                    
                    try:
                        tool_res = await tool_executor.execute(tool_name, arguments)
                    except Exception as e:
                        tool_res = f"Error during tool execution: {str(e)}"
                        
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": tool_res
                    })

            # 4. Auto-Save Findings to Memory
            try:
                summary = f"Task: {task}\nResult Summary: {final_text}"
                await memory_engine.store(
                    text=summary,
                    tags=["agent_run", self.name],
                    agent_id=self.name,
                    importance_score=0.8
                )
                self.logger.info("Saved run findings to memory for query lookup.")
            except Exception as e:
                self.logger.warning(f"Failed to save run findings to memory: {e}")
                
        finally:
            # Always Publish AgentStopped Event
            stop_event = Event(
                event_type="AgentStopped",
                actor=f"agent:{self.name}",
                workspace=workspace.name,
                data={"result": final_text}
            )
            await event_bus.publish(stop_event)

        return AgentResult(text=final_text, messages=self.messages)

