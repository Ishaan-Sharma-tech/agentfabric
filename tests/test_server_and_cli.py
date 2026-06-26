import os
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import agent_fabric
from agent_fabric.core.config import settings
from agent_fabric.core.models import Event
from agent_fabric.core.events import event_bus
from agent_fabric.server.app import create_app
from agent_fabric.cli.main import app as cli_app
from agent_fabric.observability.event_store import event_store


# --- API Server Tests ---

def test_api_server_endpoints():
    """Test REST endpoints on the FastAPI server."""
    with TemporaryDirectory() as temp_dir:
        old_dir = settings.agentfabric_dir
        settings.agentfabric_dir = Path(temp_dir)
        
        try:
            app = create_app()
            client = TestClient(app)
            
            # Ensure event store is clean
            event_store._ensure_table()
            
            # 1. Test Workspaces list & create
            res = client.get("/workspaces")
            assert res.status_code == 200
            assert len(res.json()) >= 1
            
            res_create = client.post("/workspaces", json={"name": "new_workspace"})
            assert res_create.status_code == 200
            assert res_create.json()["name"] == "new_workspace"
            
            # 2. Test Memory Store
            res_store = client.post("/memory/store", json={
                "text": "The server endpoints are fully implemented.",
                "tags": ["api", "testing"]
            })
            assert res_store.status_code == 200
            assert "id" in res_store.json()
            
            # 3. Test Memory Search
            res_search = client.get("/memory/search?query=endpoints")
            assert res_search.status_code == 200
            assert len(res_search.json()) >= 1
            assert "fully implemented" in res_search.json()[0]["text"]
            
        finally:
            settings.agentfabric_dir = old_dir


@pytest.mark.asyncio
async def test_api_server_websocket():
    """Test that the WebSocket event endpoint streams EventBus updates to the client."""
    with TemporaryDirectory() as temp_dir:
        old_dir = settings.agentfabric_dir
        settings.agentfabric_dir = Path(temp_dir)
        
        try:
            app = create_app()
            client = TestClient(app)
            event_store._ensure_table()
            
            # 1. Connect to WebSocket
            # TestClient supports synchronous websocket connections
            with client.websocket_connect("/events") as websocket:
                # 2. Publish an event on the EventBus
                test_event = Event(
                    event_type="AgentStarted",
                    actor="test_socket",
                    workspace="default",
                    data={"test": "socket"}
                )
                # Run the publish concurrently
                await event_bus.publish(test_event)
                
                # 3. Receive event from WebSocket client
                data = websocket.receive_json()
                assert data["event_type"] == "AgentStarted"
                assert data["actor"] == "test_socket"
                assert data["data"]["test"] == "socket"
                
        finally:
            settings.agentfabric_dir = old_dir


# --- CLI Command Tests ---

def test_cli_workspace_commands():
    """Verify that Typer workspace commands list and create workspaces correctly."""
    with TemporaryDirectory() as temp_dir:
        old_dir = settings.agentfabric_dir
        old_ws = settings.current_workspace
        settings.agentfabric_dir = Path(temp_dir)
        settings.current_workspace = "default"
        
        try:
            runner = CliRunner()
            
            # Test workspace list
            res_list = runner.invoke(cli_app, ["workspace", "list"])
            assert res_list.exit_code == 0
            assert "default" in res_list.stdout
            
            # Test workspace create
            res_create = runner.invoke(cli_app, ["workspace", "create", "test-cli-ws"])
            assert res_create.exit_code == 0
            assert "test-cli-ws" in res_create.stdout
            
            # Test workspace select
            res_select = runner.invoke(cli_app, ["workspace", "select", "test-cli-ws"])
            assert res_select.exit_code == 0
            assert "Switched active workspace" in res_select.stdout
            assert settings.current_workspace == "test-cli-ws"
            
        finally:
            settings.agentfabric_dir = old_dir
            settings.current_workspace = old_ws


# --- SDK Shortcut Tests ---

@patch("agent_fabric.runtime.agent.Agent.run")
def test_sdk_run_shortcut(mock_agent_run):
    """Verify that agent_fabric.run() shortcut initializes and executes synchronously."""
    # Setup mock return value
    from agent_fabric.runtime.agent import AgentResult
    mock_agent_run.return_value = AgentResult(text="Shortcut Success", messages=[])
    
    # Run shortcut synchronously with ollama provider (requires no keys or SDK imports)
    res = agent_fabric.run("This is a simple shortcut task", provider="ollama")
    
    assert res.text == "Shortcut Success"
    mock_agent_run.assert_called_once()
