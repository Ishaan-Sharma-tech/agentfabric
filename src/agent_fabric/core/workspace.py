from contextvars import ContextVar
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Dict, Any
from datetime import datetime
from agent_fabric.core.config import settings
from agent_fabric.core.models import WorkspaceConfig


# Context-local storage for workspace switching in async tasks
_current_workspace_var: ContextVar[str] = ContextVar("current_workspace")


class Workspace:
    """
    Represents an isolated workspace inside AgentFabric.
    Manages directories, SQLite databases, and workspace-specific configurations.
    """
    def __init__(self, name: str):
        self.name = name
        self.path = settings.agentfabric_dir / "workspaces" / name
        self.db_path = self.path / "agentfabric.db"
        self.logs_path = self.path / "logs"
        self.ensure_exists()

    def ensure_exists(self) -> None:
        """Create workspace directories if they do not exist."""
        self.path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

    def get_config(self) -> WorkspaceConfig:
        """Get the configuration metadata for this workspace."""
        return WorkspaceConfig(
            name=self.name,
            path=str(self.path),
            created_at=datetime.fromtimestamp(self.path.stat().st_ctime),
            active=(Workspace.current().name == self.name)
        )

    @classmethod
    def current(cls) -> "Workspace":
        """
        Get the current active workspace.
        Resolves context-local workspace first, falling back to global settings.
        """
        try:
            name = _current_workspace_var.get()
        except LookupError:
            name = settings.current_workspace
        return cls(name)

    @classmethod
    def get(cls, name: str) -> "Workspace":
        """Get a workspace instance by name (creates it if missing)."""
        return cls(name)

    @classmethod
    @contextmanager
    def use(cls, name: str) -> Generator["Workspace", None, None]:
        """
        Context manager to switch workspaces within a thread/async context.
        Usage:
            with Workspace.use("my-workspace"):
                # operations run inside my-workspace context
                pass
        """
        token = _current_workspace_var.set(name)
        try:
            yield cls(name)
        finally:
            _current_workspace_var.reset(token)

    @classmethod
    def list_all(cls) -> list["Workspace"]:
        """List all workspaces registered in the system."""
        workspaces_dir = settings.agentfabric_dir / "workspaces"
        if not workspaces_dir.exists():
            return [cls(settings.current_workspace)]
        
        names = [d.name for d in workspaces_dir.iterdir() if d.is_dir()]
        if not names:
            names = [settings.current_workspace]
            
        return [cls(name) for name in sorted(list(set(names)))]

    def __repr__(self) -> str:
        return f"Workspace(name='{self.name}', path='{self.path}')"
