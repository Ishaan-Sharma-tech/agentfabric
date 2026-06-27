import subprocess
from agent_fabric.tools.decorator import tool
from agent_fabric.core.workspace import Workspace

__all__ = ["shell_execute"]


@tool("Execute shell command inside workspace sandbox")
def shell_execute(command: str, timeout: int = 30) -> str:
    """Executes a shell command inside the workspace directory and returns stdout/stderr output."""
    try:
        workspace = Workspace.current()
        res = subprocess.run(
            command,
            shell=True,
            cwd=str(workspace.path),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = res.stdout
        if res.stderr:
            output += "\nSTDERR:\n" + res.stderr
        return output if output.strip() else f"Command completed with exit code {res.returncode}."
    except subprocess.TimeoutExpired:
        return f"Error: Command execution timed out after {timeout} seconds."
    except Exception as e:
        return f"Failed to execute command '{command}': {e}"
