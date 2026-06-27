import time
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event
from agent_fabric.core.workspace import Workspace

logger = logging.getLogger("agent_fabric.runtime.mailbox")

__all__ = ["AgentMessage", "Mailbox"]


class AgentMessage(BaseModel):
    """Structured message passed between agents in multi-agent workflows."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    sender: str
    recipient: str
    message_type: str = "task"  # task, result, feedback, delegation
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class Mailbox:
    """
    Asynchronous message mailbox for an agent.
    Communicates across agents using EventBus broadcasts and isolated internal queues.
    """
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self._queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._subscribed = False

    def start(self) -> None:
        """Subscribe to AgentMessage events on the global EventBus."""
        if not self._subscribed:
            event_bus.subscribe("AgentMessage", self._on_event)
            self._subscribed = True

    def stop(self) -> None:
        """Unsubscribe from AgentMessage events on the global EventBus."""
        if self._subscribed:
            event_bus.unsubscribe("AgentMessage", self._on_event)
            self._subscribed = False

    async def _on_event(self, event: Event) -> None:
        """Internal callback filtering events addressed to this mailbox's agent."""
        data = event.data
        recipient = data.get("recipient")
        if recipient in (self.agent_name, "*"):
            try:
                msg = AgentMessage(**data)
                await self._queue.put(msg)
            except Exception as e:
                logger.warning(f"Failed to parse AgentMessage in mailbox '{self.agent_name}': {e}")

    async def send(
        self, 
        recipient: str, 
        message_type: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentMessage:
        """Construct and publish a message to a recipient agent via EventBus."""
        workspace = Workspace.current()
        msg = AgentMessage(
            sender=self.agent_name,
            recipient=recipient,
            message_type=message_type,
            content=content,
            metadata=metadata or {}
        )
        event = Event(
            event_type="AgentMessage",
            actor=f"agent:{self.agent_name}",
            workspace=workspace.name,
            data=msg.model_dump()
        )
        await event_bus.publish(event)
        return msg

    async def receive(self, timeout: Optional[float] = None) -> AgentMessage:
        """Retrieve the next message addressed to this agent, with optional timeout."""
        if not self._subscribed:
            self.start()
            
        if timeout is not None:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        return await self._queue.get()
