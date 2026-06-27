from pathlib import Path
from agent_fabric.tools.decorator import tool
from agent_fabric.core.workspace import Workspace
from agent_fabric.core.config import settings

__all__ = ["read_file", "write_file"]


import tempfile

def _validate_safe_path(path_str: str) -> Path:
    """Validate that the given path is contained within the current workspace, agentfabric root, or temp directory."""
    ws = Workspace.current()
    ws_root = ws.path.resolve()
    base_root = settings.agentfabric_dir.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    
    target = Path(path_str)
    if not target.is_absolute():
        target = ws_root / target
    resolved = target.resolve()
    
    # Verify path containment
    res_str = str(resolved)
    if not (res_str.startswith(str(ws_root)) or res_str.startswith(str(base_root)) or res_str.startswith(str(temp_root))):
        raise PermissionError(f"Access denied: Path '{path_str}' is outside active workspace '{ws.name}'.")
    return resolved


@tool(name="read_file", description="Read the entire contents of a text file from the active workspace filesystem.")
def read_file(path: str) -> str:
    """
    Read content of file at path within the active workspace.
    """
    try:
        file_path = _validate_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error resolving path '{path}': {e}"

    if not file_path.exists():
        return f"Error: File at '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."
        
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file '{path}': {type(e).__name__}: {str(e)}"


@tool(name="write_file", description="Write content to a text file within the active workspace filesystem. Overwrites the file if it exists.")
def write_file(path: str, content: str) -> str:
    """
    Write content to file at path within active workspace, creating parent directories if missing.
    """
    try:
        file_path = _validate_safe_path(path)
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error resolving path '{path}': {e}"

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote content to file '{path}'."
    except Exception as e:
        return f"Error writing file '{path}': {type(e).__name__}: {str(e)}"

