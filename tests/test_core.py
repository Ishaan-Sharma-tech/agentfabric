import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from agent_fabric.core.config import AgentFabricSettings, load_settings, DEFAULT_AGENTFABRIC_DIR
from agent_fabric.core.models import Event, AgentConfig, MemoryRecord
from agent_fabric.core.events import EventBus
from agent_fabric.core.permissions import Capability, check_permission
from agent_fabric.core.workspace import Workspace


def test_settings_load(monkeypatch):
    """Test that settings load properly and environment variables override defaults."""
    # Test defaults
    settings = load_settings()
    assert settings.current_workspace == "default"
    assert settings.default_provider == "openai"
    assert settings.providers.openai_model == "gpt-4o-mini"
    
    # Test env overrides
    monkeypatch.setenv("AGENTFABRIC_WORKSPACE", "custom-workspace")
    monkeypatch.setenv("AGENTFABRIC_DEFAULT_PROVIDER", "google")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    
    overridden = load_settings()
    assert overridden.current_workspace == "custom-workspace"
    assert overridden.default_provider == "google"
    assert overridden.providers.get_key_str("openai_api_key") == "test-openai-key"


@pytest.mark.asyncio
async def test_event_bus():
    """Test publish-subscribe and request-response patterns on EventBus."""
    bus = EventBus()
    events_received = []

    # 1. Test standard subscription
    async def handler(event: Event):
        events_received.append(event)

    bus.subscribe("test_event", handler)

    test_event = Event(event_type="test_event", data={"key": "val"})
    await bus.publish(test_event)
    
    # Give async handlers a moment to run (though gather runs immediately)
    assert len(events_received) == 1
    assert events_received[0].data["key"] == "val"

    # 2. Test wildcard subscription
    wildcard_events = []
    async def wildcard_handler(event: Event):
        wildcard_events.append(event)
    
    bus.subscribe("*", wildcard_handler)
    await bus.publish(test_event)
    assert len(wildcard_events) == 1

    # 3. Test request-response RPC
    async def request_handler(event: Event):
        return f"Hello, {event.data.get('name')}"

    bus.register_request_handler("rpc_request", request_handler)
    
    req_event = Event(event_type="rpc_request", data={"name": "Alice"})
    response = await bus.request(req_event)
    assert response == "Hello, Alice"


def test_permissions():
    """Test capability matching rules (action, resource, scope, and paths)."""
    # Exact match
    granted = Capability(resource="file", action="read", scope="/path/to/dir")
    req_exact = Capability(resource="file", action="read", scope="/path/to/dir")
    assert granted.matches(req_exact)

    # Action wildcard
    granted_wildcard = Capability(resource="file", action="*", scope="/path/to/dir")
    assert granted_wildcard.matches(req_exact)

    # Resource wildcard
    granted_res_wild = Capability(resource="*", action="*", scope="*")
    assert granted_res_wild.matches(req_exact)

    # Path prefix check
    granted_parent = Capability(resource="file", action="read", scope=str(Path("/path/to").resolve()))
    req_child = Capability(resource="file", action="read", scope=str(Path("/path/to/dir/file.txt").resolve()))
    assert granted_parent.matches(req_child)

    # Path check mismatch (not child)
    granted_sibling = Capability(resource="file", action="read", scope=str(Path("/path/other").resolve()))
    assert not granted_sibling.matches(req_child)

    # Glob matching
    granted_glob = Capability(resource="network", action="execute", scope="*.openai.com")
    req_domain = Capability(resource="network", action="execute", scope="api.openai.com")
    assert granted_glob.matches(req_domain)
    
    req_wrong_domain = Capability(resource="network", action="execute", scope="openai.com.hacker.com")
    assert not granted_glob.matches(req_wrong_domain)


def test_workspaces():
    """Test switching workspaces and directory generation."""
    with TemporaryDirectory() as temp_dir:
        # Override settings for tests
        import agent_fabric.core.workspace as ws
        old_dir = ws.settings.agentfabric_dir
        ws.settings.agentfabric_dir = Path(temp_dir)
        
        try:
            # Create a workspace
            workspace_name = "test-ws"
            workspace = Workspace.get(workspace_name)
            
            assert workspace.name == "test-ws"
            assert workspace.path == Path(temp_dir) / "workspaces" / "test-ws"
            assert workspace.path.exists()
            assert workspace.logs_path.exists()
            
            # Test default workspace is active initially
            assert Workspace.current().name == "default"
            
            # Switch using context manager
            with Workspace.use("test-ws"):
                assert Workspace.current().name == "test-ws"
                
            # Verify it reverts back
            assert Workspace.current().name == "default"
            
        finally:
            ws.settings.agentfabric_dir = old_dir
