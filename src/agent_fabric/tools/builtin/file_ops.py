import os
from pathlib import Path
from agent_fabric.tools.decorator import tool


@tool(name="read_file", description="Read the entire contents of a text file from the local filesystem.")
def read_file(path: str) -> str:
    """
    Read content of file at path.
    """
    file_path = Path(path).resolve()
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


@tool(name="write_file", description="Write content to a text file on the local filesystem. Overwrites the file if it exists.")
def write_file(path: str, content: str) -> str:
    """
    Write content to file at path, creating parent directories if missing.
    """
    file_path = Path(path).resolve()
    try:
        # Create directories if missing
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote content to file '{path}'."
    except Exception as e:
        return f"Error writing file '{path}': {type(e).__name__}: {str(e)}"
