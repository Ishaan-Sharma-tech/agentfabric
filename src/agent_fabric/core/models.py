from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for an Agent instance."""
    name: str
    provider: str = Field(default="openai")
    model: Optional[str] = Field(default=None)
    system_prompt: Optional[str] = Field(default=None)
    tools: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    workspace: str = Field(default="default")
    temperature: float = Field(default=0.7)
    max_tokens: Optional[int] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Data representation of a single tool execution."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = Field(default=None)


class Event(BaseModel):
    """A structured event emitted in the AgentFabric EventBus."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = Field(default_factory=dict)
    actor: Optional[str] = Field(default=None)  # e.g. "agent:researcher", "system", "cli"
    workspace: str = Field(default="default")


class MemoryRecord(BaseModel):
    """A single record stored in the memory engine."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    embedding: Optional[List[float]] = Field(default=None)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    agent_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    importance_score: float = Field(default=1.0)


class WorkspaceConfig(BaseModel):
    """Configuration metadata for a workspace."""
    name: str
    path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = Field(default=True)
    metadata: Dict[str, Any] = Field(default_factory=dict)
