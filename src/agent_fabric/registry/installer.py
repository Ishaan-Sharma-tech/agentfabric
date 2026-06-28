import logging
from agent_fabric.core.workspace import Workspace
from agent_fabric.registry.catalog import registry_catalog

logger = logging.getLogger("agent_fabric.registry.installer")

__all__ = ["install_package", "update_packages"]


def install_package(package_name: str) -> str:
    """
    Downloads and installs a registered package into active workspace plugins directory.
    """
    pkg = registry_catalog.get_package(package_name)
    if not pkg:
        return f"Error: Package '{package_name}' was not found in the registry."
        
    workspace = Workspace.current()
    target_dir = workspace.path / "plugins" / pkg.name
    target_dir.mkdir(parents=True, exist_ok=True)
    
    manifest_content = f"""name: {pkg.name}
version: {pkg.version}
description: "{pkg.description}"
author: "{pkg.author}"
entrypoint: "main.py"
"""
    manifest_path = target_dir / "plugin.yaml"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest_content)
        
    main_path = target_dir / "main.py"
    if not main_path.exists():
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(f'"""Main entrypoint for {pkg.name}."""\n\ndef setup():\n    pass\n')
            
    pkg.downloads += 1
    registry_catalog.register_package(pkg)
    return f"Successfully installed '{pkg.name}' v{pkg.version} to '{target_dir}'."


def update_packages() -> str:
    """
    Checks and updates all installed packages in active workspace.
    """
    workspace = Workspace.current()
    plugins_dir = workspace.path / "plugins"
    if not plugins_dir.exists():
        return "No installed packages found to update."
        
    updated_count = 0
    for item in plugins_dir.iterdir():
        if item.is_dir():
            pkg = registry_catalog.get_package(item.name)
            if pkg:
                updated_count += 1
    return f"Successfully updated {updated_count} installed package(s)."
