import logging
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from agent_fabric.core.config import settings
from agent_fabric.core.models import Event, AgentConfig
from agent_fabric.core.permissions import Capability, DEVELOPER_CAPABILITIES
from agent_fabric.core.events import event_bus
from agent_fabric.core.workspace import Workspace
from agent_fabric.memory.engine import memory_engine
from agent_fabric.tools.registry import tool_registry
from agent_fabric.tools.runtime import ToolExecutor
from agent_fabric.providers.openai import OpenAIProvider
from agent_fabric.providers.ollama import OllamaProvider
from agent_fabric.observability.logger import setup_agent_logger

logger = logging.getLogger("agent_fabric.runtime.agent")


class AgentResult(BaseModel):
    """Result returned by an Agent execution run."""
    text: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)


class Agent:
    """
    The Agent class handles the conversational execution loop, tool invocation,
    conversational history, and automatic memory integration.
    """
    def __init__(
        self,
        name: str,
        model: Optional[str] = None,
        tools: Optional[List[Union[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        provider: Optional[Union[str, Any]] = None,
        capabilities: Optional[List[Capability]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt or f"You are a helpful AI assistant named {name}."
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Isolated agent logger setup
        self.logger = setup_agent_logger(name)
        
        # Capability checks default to DEVELOPER_CAPABILITIES (permissive developer defaults)
        self.capabilities = capabilities or DEVELOPER_CAPABILITIES
        
        # Resolve LLM Provider
        provider_name = provider or settings.default_provider
        if isinstance(provider_name, str):
            if provider_name == "openai":
                self.provider = OpenAIProvider(default_model=model)
            elif provider_name == "ollama":
                self.provider = OllamaProvider(default_model=model)
            else:
                raise ValueError(f"Unsupported built-in provider: {provider_name}")
        else:
            # Custom provider conforming to LLMProvider protocol
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
        import json
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

        # 1. Retrieve Context from Memory Engine (Automatic Context Memory Injection)
        memories = await memory_engine.search(task, limit=3)
        if memories:
            context_snippet = "\n".join([f"- {m.text}" for m in memories])
            system_injection = (
                f"\n\n[CONTEXT MEMORY] Here is relevant context retrieved from your memory store:\n"
                f"{context_snippet}"
            )
            # Find system message and append context snippet
            for msg in self.messages:
                if msg["role"] == "system":
                    msg["content"] += system_injection
                    break

        # 2. Append User Task to message history
        self.messages.append({"role": "user", "content": task})

        # 3. Agent Execution Loop
        tool_executor = ToolExecutor(self.name, self.capabilities)
        step = 0
        final_text = ""
        
        while step < max_steps:
            step += 1
            self.logger.info(f"Agent execution loop step {step}/{max_steps}")
            
            # Request LLM chat completion
            response = await self.provider.chat(
                messages=self.messages,
                tools=self.tools,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Format assistant message for history
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response["content"]
            }
            if response.get("tool_calls"):
                assistant_msg["tool_calls"] = response["tool_calls"]
            self.messages.append(assistant_msg)
            
            final_text = response["content"]
            tool_calls = response.get("tool_calls", [])
            
            if not tool_calls:
                # Execution loop finished
                self.logger.info("Agent loop finished executing.")
                break
                
            # Execute tool calls
            for tc in tool_calls:
                call_id = tc["id"]
                tool_name = tc["name"]
                arguments = tc["arguments"]
                
                try:
                    tool_res = await tool_executor.execute(tool_name, arguments)
                except Exception as e:
                    tool_res = f"Error during tool execution: {str(e)}"
                    
                # Append tool result to conversation history
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": tool_name,
                    "content": tool_res
                })

        # 4. Auto-Save Findings to Memory
        summary = f"Task: {task}\nResult Summary: {final_text}"
        await memory_engine.store(
            text=summary,
            tags=["agent_run", self.name],
            agent_id=self.name,
            importance_score=0.8
        )
        self.logger.info(f"Saved run findings to memory for query lookup.")

        # Publish AgentStopped Event
        stop_event = Event(
            event_type="AgentStopped",
            actor=f"agent:{self.name}",
            workspace=workspace.name,
            data={"result": final_text}
        )
        await event_bus.publish(stop_event)

        return AgentResult(text=final_text, messages=self.messages)
