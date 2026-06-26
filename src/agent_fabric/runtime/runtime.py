from typing import Optional
from agent_fabric.core.config import settings
from agent_fabric.core.workspace import Workspace


class Runtime:
    """
    Runtime manager for AgentFabric.
    Enables advanced programmers to customize backend drivers, active providers,
    and workspace isolation contexts programmatically.
    """
    def __init__(
        self,
        memory_backend: Optional[str] = None,
        provider: Optional[str] = None,
        workspace: Optional[str] = None
    ) -> None:
        if memory_backend:
            settings.memory_backend = memory_backend
            
        if provider:
            settings.default_provider = provider
            
        if workspace:
            settings.current_workspace = workspace
            Workspace.get(workspace).ensure_exists()

    @property
    def active_workspace(self) -> Workspace:
        """Returns the current active workspace."""
        return Workspace.current()

    @property
    def settings(self):
        """Access global runtime settings."""
        return settings
