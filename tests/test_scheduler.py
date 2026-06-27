import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event
from agent_fabric.scheduler.scheduler import Schedule, SchedulerEngine
from agent_fabric.scheduler.history import ScheduleHistoryStore
from agent_fabric.server.app import create_app


@pytest.fixture(autouse=True)
def mock_openai_environment():
    with patch("agent_fabric.providers.openai.OPENAI_AVAILABLE", True), \
         patch("agent_fabric.providers.openai.AsyncOpenAI", create=True) as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_scheduler_target_execution(tmp_path):
    """Verify executing scheduled targets records start, complete, and output history."""
    db_file = str(tmp_path / "test_sched.db")
    history = ScheduleHistoryStore(db_file)
    engine = SchedulerEngine(history)
    
    with patch("agent_fabric.tools.registry.tool_registry.get") as mock_tool_get:
        mock_tool = AsyncMock()
        mock_tool.execute.return_value = "Tool execution success"
        mock_tool_get.return_value = mock_tool
        
        schedule = Schedule(
            name="test_tool_job",
            trigger_type="interval",
            trigger_config={"seconds": 10},
            target_type="tool",
            target_name="test_tool",
            inputs={"param": "value"}
        )
        
        engine.create_schedule(schedule)
        out = await engine.execute_target(schedule)
        assert out == "Tool execution success"
        
        hist_records = engine.history_store.get_history(schedule.id)
        assert len(hist_records) == 1
        assert hist_records[0].status == "completed"
        assert hist_records[0].output == "Tool execution success"
        
        engine.delete_schedule(schedule.id)


@pytest.mark.asyncio
async def test_event_driven_schedule(tmp_path):
    """Verify reactive EventBus event triggers execute scheduled workloads."""
    db_file = str(tmp_path / "test_event_sched.db")
    history = ScheduleHistoryStore(db_file)
    engine = SchedulerEngine(history)
    
    executed_event = asyncio.Event()
    
    async def mock_execute_target(schedule):
        executed_event.set()
        return "Event target done"
        
    engine.execute_target = mock_execute_target
    
    schedule = Schedule(
        name="on_custom_event",
        trigger_type="event",
        trigger_config={"event_type": "UserActionTriggered"},
        target_type="tool",
        target_name="dummy_tool"
    )
    
    engine.create_schedule(schedule)
    
    # Fire EventBus event
    await event_bus.publish(Event(event_type="UserActionTriggered", actor="test", workspace="default", data={}))
    
    try:
        await asyncio.wait_for(executed_event.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        pytest.fail("Event driven schedule failed to trigger within timeout.")
    finally:
        engine.delete_schedule(schedule.id)


def test_api_scheduler_endpoints(tmp_path):
    """Verify REST API routes for schedule management."""
    app = create_app()
    client = TestClient(app)
    
    # Create schedule via POST /schedules
    res_create = client.post("/schedules", json={
        "name": "api_sched",
        "trigger_type": "interval",
        "trigger_config": {"seconds": 300},
        "target_type": "tool",
        "target_name": "web_search",
        "inputs": {"query": "AI news"}
    })
    assert res_create.status_code == 200
    data_create = res_create.json()
    sched_id = data_create["id"]
    assert data_create["name"] == "api_sched"
    
    # List schedules via GET /schedules
    res_list = client.get("/schedules")
    assert res_list.status_code == 200
    schedules = res_list.json()
    assert any(s["id"] == sched_id for s in schedules)
    
    # Pause schedule via PUT /schedules/{id}/pause
    res_pause = client.put(f"/schedules/{sched_id}/pause")
    assert res_pause.status_code == 200
    
    # Get history via GET /schedules/{id}/history
    res_hist = client.get(f"/schedules/{sched_id}/history")
    assert res_hist.status_code == 200
    
    # Delete schedule via DELETE /schedules/{id}
    res_del = client.delete(f"/schedules/{sched_id}")
    assert res_del.status_code == 200
