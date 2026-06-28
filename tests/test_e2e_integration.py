import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from agent_fabric.runtime.agent import Agent
from agent_fabric.adapters.generic import GenericAgentAdapter
from agent_fabric.runtime.team import Team
from agent_fabric.pipelines.dag import Pipeline, PipelineNode, PipelineEdge
from agent_fabric.pipelines.executor import PipelineExecutor
from agent_fabric.scheduler.scheduler import Schedule, SchedulerEngine
from agent_fabric.plugins.manifest import PluginManifest
from agent_fabric.mcp.server import MCPServer
from agent_fabric.memory.consolidation import MemoryConsolidator
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore


@pytest.fixture
def mock_provider():
    p = AsyncMock()
    p.default_model = "mock-model"
    p.chat.return_value = {"content": "Mock E2E response", "tool_calls": []}
    return p


@pytest.mark.asyncio
async def test_e2e_full_agentfabric_stack(mock_provider):
    """Validates full E2E stack integrations across all components."""
    # 1. Single Agent Flow
    agent = Agent("e2e-agent", provider=mock_provider)
    res1 = await agent.run("E2E Test task")
    assert res1.text == "Mock E2E response"

    # 2. BYOA Wrapper Flow
    class Legacy:
        def run(self, msg: str) -> str:
            return f"Done: {msg}"
    adapter = GenericAgentAdapter(target_agent=Legacy(), name="legacy_bot", memory=False, observe=False)
    res2 = await adapter.run("BYOA task")
    assert "Done:" in res2.text

    # 3. Multi-agent Team Flow
    team = Team(agents=[Agent("a1", provider=mock_provider), Agent("a2", provider=mock_provider)], strategy="sequential")
    res3 = await team.run("Team task")
    assert res3.text is not None

    # 4. Pipeline Execution
    pipe = Pipeline(id="e2e-pipe", name="E2E Pipe", nodes=[PipelineNode(id="n1", type="transform", config={"template": "hello"})], edges=[])
    executor = PipelineExecutor(pipe)
    run_rec = await executor.run()
    assert "n1" in run_rec.outputs

    # 5. Scheduler Engine
    engine = SchedulerEngine()
    sched = Schedule(name="e2e-cron", trigger_type="cron", trigger_config={"cron_expression": "*/10 * * * *"}, target_type="agent", target_name="a1")
    engine.create_schedule(sched)
    assert len(engine.list_schedules()) >= 1
    engine.delete_schedule(sched.id)

    # 6. Plugin Manifest
    pm = PluginManifest(name="e2e-plugin", version="1.0.0", description="E2E Plugin", author="Test")
    assert pm.name == "e2e-plugin"

    # 7. MCP Server
    mcp = MCPServer()
    init_res = await mcp.handle_jsonrpc_request('{"jsonrpc":"2.0","id":100,"method":"initialize"}')
    assert "result" in init_res

    # 8. Memory Consolidation
    store = SQLiteMemoryStore()
    consolidator = MemoryConsolidator(store=store)
    cons = await consolidator.consolidate()
    assert cons.text is not None
