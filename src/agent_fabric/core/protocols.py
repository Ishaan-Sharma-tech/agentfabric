from typing import Protocol, List, Dict, Any, Optional, AsyncIterator, runtime_checkable
from agent_fabric.core.models import MemoryRecord


@runtime_checkable
class ToolProtocol(Protocol):
    """
    Protocol definition for tools that can be registered and run in AgentFabric.
    Any class implementing these properties and methods is recognized as a tool.
    """
    @property
    def name(self) -> str:
        """The name of the tool."""
        ...

    @property
    def description(self) -> str:
        """A detailed description of what the tool does."""
        ...

    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema dictionary defining the arguments accepted by the tool."""
        ...

    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool asynchronously with the given arguments.
        Must return a string or an object that can be serialized/stringified.
        """
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """
    Protocol definition for LLM providers (OpenAI, Anthropic, Google, Ollama, etc.).
    Allows the agent runtime to interact with any language model.
    """
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to the LLM.
        Returns a dictionary containing the response text and any tool calls.
        Format:
        {
            "role": "assistant",
            "content": "...",
            "tool_calls": [{"id": "...", "name": "...", "arguments": {...}}]
        }
        """
        ...

    async def stream(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream the completion response from the LLM.
        Yields chunks of the response.
        """
        ...


@runtime_checkable
class MemoryBackend(Protocol):
    """
    Protocol definition for memory backend implementations (SQLite, Qdrant, etc.).
    """
    async def store(self, record: MemoryRecord) -> None:
        """Store a memory record in the backend."""
        ...

    async def search(
        self, 
        query: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """Search for memories matching the query (semantic or full-text)."""
        ...

    async def delete(self, record_id: str) -> None:
        """Delete a memory record by its ID."""
        ...

    async def list_records(
        self, 
        limit: int = 100, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """List stored memories with optional filtering."""
        ...
