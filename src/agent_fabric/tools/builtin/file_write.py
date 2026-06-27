from agent_fabric.tools.decorator import tool
from agent_fabric.core.workspace import Workspace

__all__ = ["file_write"]


@tool("Write text content to local file")
def file_write(filepath: str, content: str) -> str:
    """Writes or overwrites text content into a specified file path inside the active workspace."""
    try:
        workspace = Workspace.current()
        target_path = (workspace.path / filepath).resolve()
        if not str(target_path).startswith(str(workspace.path.resolve())):
            return f"Error: Filepath '{filepath}' is outside the active workspace sandbox."
            
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to '{filepath}'."
    except Exception as e:
        return f"Failed to write file '{filepath}': {e}"
