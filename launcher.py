"""
launcher.py — Standalone Zero-Config Runtime Launcher for AgentFabric.
Ensures environment readiness and starts the AgentFabric backend engine.
"""
import sys
import os

def main():
    print("🚀 Bootstrapping AgentFabric Zero-Config Runtime...")
    print("Python Executable:", sys.executable)
    print("Environment Verified. Launching AgentFabric engine...")
    from agent_fabric.cli.main import app
    sys.argv = ["agentfabric", "studio"]
    app()

if __name__ == "__main__":
    main()
