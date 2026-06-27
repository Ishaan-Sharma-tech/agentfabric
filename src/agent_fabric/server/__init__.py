"""
AgentFabric REST and WebSocket server API.
Exposes REST and WebSocket endpoints for controlling and monitoring the AgentFabric runtime.
"""
from agent_fabric.server.app import create_app as create_app

__all__ = ["create_app"]
