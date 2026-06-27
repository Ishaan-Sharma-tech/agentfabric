import logging
import threading
from typing import Dict, List, Optional
from agent_fabric.core.protocols import ToolProtocol

logger = logging.getLogger("agent_fabric.tools.registry")

__all__ = ["ToolRegistry", "tool_registry"]


class ToolRegistry:
    """
    Registry for discovering and managing tools within AgentFabric.
    Thread-safe implementation.
    """
    def __init__(self) -> None:
        self._tools: Dict[str, ToolProtocol] = {}
        self._lock = threading.Lock()

    def register(self, tool_instance: ToolProtocol) -> None:
        """Register a tool instance in the registry."""
        name = tool_instance.name
        with self._lock:
            if name in self._tools:
                logger.warning(f"Overwriting registered tool: {name}")
            self._tools[name] = tool_instance
        logger.debug(f"Registered tool: {name}")

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.debug(f"Unregistered tool: {name}")

    def get(self, name: str) -> Optional[ToolProtocol]:
        """Retrieve a registered tool by name."""
        with self._lock:
            return self._tools.get(name)

    def list_all(self) -> List[ToolProtocol]:
        """List all currently registered tools."""
        with self._lock:
            return list(self._tools.values())

    def clear(self) -> None:
        """Clear all registered tools."""
        with self._lock:
            self._tools.clear()


# Global tool registry singleton
tool_registry = ToolRegistry()

