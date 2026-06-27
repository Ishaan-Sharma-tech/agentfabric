import re
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Generator, Dict, List
from datetime import datetime, timezone
from agent_fabric.core.config import settings
from agent_fabric.core.models import WorkspaceConfig


# Context-local storage for workspace switching in async tasks
_current_workspace_var: ContextVar[str] = ContextVar("current_workspace")
_workspace_cache: Dict[str, "Workspace"] = {}

WORKSPACE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def validate_workspace_name(name: str) -> str:
    """Validate that workspace name is safe against path traversal."""
    if not isinstance(name, str) or not WORKSPACE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid workspace name: {name!r}. Must match pattern '^[a-zA-Z0-9][a-zA-Z0-9._-]{{0,63}}$'."
        )
    return name


class Workspace:
    """
    Represents an isolated workspace inside AgentFabric.
    Manages directories, SQLite databases, and workspace-specific configurations.
    """
    def __init__(self, name: str):
        self.name = validate_workspace_name(name)
        workspaces_root = (settings.agentfabric_dir / "workspaces").resolve()
        target_path = (workspaces_root / self.name).resolve()
        
        # Verify path containment
        if not str(target_path).startswith(str(workspaces_root)):
            raise ValueError(f"Workspace path escapes workspaces directory: {target_path}")

        self.path = target_path
        self.db_path = self.path / "agentfabric.db"
        self.logs_path = self.path / "logs"
        self.ensure_exists()

    def ensure_exists(self) -> None:
        """Create workspace directories if they do not exist."""
        self.path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

    def get_config(self) -> WorkspaceConfig:
        """Get the configuration metadata for this workspace."""
        st_ctime = self.path.stat().st_ctime
        return WorkspaceConfig(
            name=self.name,
            path=str(self.path),
            created_at=datetime.fromtimestamp(st_ctime, tz=timezone.utc),
            active=(Workspace.current_name() == self.name)
        )

    @classmethod
    def current_name(cls) -> str:
        """Get the name of the current active workspace without instantiating it."""
        try:
            return _current_workspace_var.get()
        except LookupError:
            return settings.current_workspace

    @classmethod
    def current(cls) -> "Workspace":
        """
        Get the current active workspace.
        Resolves context-local workspace first, falling back to global settings.
        """
        return cls.get(cls.current_name())

    @classmethod
    def get(cls, name: str) -> "Workspace":
        """Get a workspace instance by name (cached per root path)."""
        clean_name = validate_workspace_name(name)
        workspaces_root = (settings.agentfabric_dir / "workspaces").resolve()
        cache_key = f"{workspaces_root}::{clean_name}"
        if cache_key not in _workspace_cache:
            _workspace_cache[cache_key] = cls(clean_name)
        return _workspace_cache[cache_key]

    @classmethod
    @contextmanager
    def use(cls, name: str) -> Generator["Workspace", None, None]:
        """
        Context manager to switch workspaces within a thread/async context.
        """
        clean_name = validate_workspace_name(name)
        token = _current_workspace_var.set(clean_name)
        try:
            yield cls.get(clean_name)
        finally:
            _current_workspace_var.reset(token)

    @classmethod
    def list_all(cls) -> List["Workspace"]:
        """List all workspaces registered in the system."""
        workspaces_dir = (settings.agentfabric_dir / "workspaces").resolve()
        if not workspaces_dir.exists():
            return [cls.get(settings.current_workspace)]
        
        valid_workspaces = []
        for d in sorted(workspaces_dir.iterdir()):
            if d.is_dir():
                try:
                    valid_workspaces.append(cls.get(d.name))
                except ValueError:
                    continue

        if not valid_workspaces:
            valid_workspaces = [cls.get(settings.current_workspace)]
            
        return valid_workspaces

    def __repr__(self) -> str:
        return f"Workspace(name='{self.name}', path='{self.path}')"

