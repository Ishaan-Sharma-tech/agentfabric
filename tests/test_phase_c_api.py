import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event
from agent_fabric.server.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

@pytest.fixture(autouse=True)
def mock_openai_environment():
    with patch("agent_fabric.providers.openai.OPENAI_AVAILABLE", True), \
         patch("agent_fabric.providers.openai.AsyncOpenAI", create=True) as mock_client:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Mock API Response", tool_calls=[]))]))
        mock_client.return_value = mock_instance
        yield mock_instance

def test_phase_c_rest_endpoints(client):
    """Exhaustive Phase C testing of REST API routes."""
    # Workspaces list
    res_ws = client.get("/workspaces")
    assert res_ws.status_code == 200
    assert len(res_ws.json()) >= 1

    # Memory store & search
    res_store = client.post("/memory/store", json={"text": "Phase C REST test", "tags": ["test"]})
    assert res_store.status_code == 200

    res_search = client.get("/memory/search?query=Phase")
    assert res_search.status_code == 200

    # Registry endpoints
    res_reg = client.get("/registry/search")
    assert res_reg.status_code == 200

    # Memory backup export
    res_exp = client.post("/memory/export")
    assert res_exp.status_code == 200

@pytest.mark.asyncio
async def test_phase_c_websocket_endpoint(client):
    """Exhaustive Phase C testing of WebSocket event streaming."""
    with client.websocket_connect("/events") as websocket:
        test_event = Event(event_type="PhaseCTest", actor="tester", data={"key": "val"})
        await event_bus.publish(test_event)
        data = websocket.receive_json()
        assert data["event_type"] == "PhaseCTest"
