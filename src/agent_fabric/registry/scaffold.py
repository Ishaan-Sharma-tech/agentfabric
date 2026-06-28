import logging
from agent_fabric.core.workspace import Workspace

logger = logging.getLogger("agent_fabric.registry.scaffold")

__all__ = ["scaffold_plugin"]


def scaffold_plugin(plugin_name: str) -> str:
    """
    Scaffolds a new boilerplate plugin project directory.
    """
    workspace = Workspace.current()
    target_dir = workspace.path / "plugins" / plugin_name
    if target_dir.exists():
        return f"Error: Plugin directory '{plugin_name}' already exists in workspace."
        
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "tools").mkdir(exist_ok=True)
    (target_dir / "skills").mkdir(exist_ok=True)
    
    manifest_content = f"""name: {plugin_name}
version: 0.1.0
description: "Custom plugin scaffolded with AgentFabric CLI"
author: "Developer"
entrypoint: "main.py"
"""
    with open(target_dir / "plugin.yaml", "w", encoding="utf-8") as f:
        f.write(manifest_content)
        
    main_code = f'"""\nMain entrypoint for {plugin_name}.\n"""\nfrom agent_fabric.tools.decorator import tool\n\n@tool("Sample tool for {plugin_name}")\ndef sample_tool(text: str) -> str:\n    return f"Processed: {{text}}"\n'
    with open(target_dir / "main.py", "w", encoding="utf-8") as f:
        f.write(main_code)
        
    return f"Successfully scaffolded new plugin project at '{target_dir}'."
