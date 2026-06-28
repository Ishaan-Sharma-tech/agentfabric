"""
06_custom_plugin.py — Custom plugin creation example.
"""
from agent_fabric.plugins.manifest import PluginManifest
from agent_fabric.tools.decorator import tool

@tool(name="custom_calculator", description="Performs custom calculation.")
def custom_calculator(a: float, b: float) -> float:
    return a * b + 42.0

def main():
    manifest = PluginManifest(
        name="calculator-plugin",
        version="1.0.0",
        description="Custom calculator plugin",
        author="AgentFabric User",
        tools=["custom_calculator"]
    )
    print("Created Plugin Manifest:", manifest.name)

if __name__ == "__main__":
    main()
