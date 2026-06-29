import os
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import SecretStr
from agent_fabric.core.config import settings
from agent_fabric.runtime.agent import Agent
from agent_fabric.runtime.team import Team
from agent_fabric.pipelines.dag import Pipeline, PipelineNode, PipelineEdge
from agent_fabric.pipelines.executor import PipelineExecutor
from agent_fabric.scheduler.scheduler import Schedule, SchedulerEngine
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore
from agent_fabric.memory.consolidation import MemoryConsolidator
from agent_fabric.memory.forgetting import ForgettingPolicy
from agent_fabric.memory.knowledge_graph import KnowledgeGraph
from agent_fabric.memory.shared import shared_memory
from agent_fabric.adapters.generic import GenericAgentAdapter
from agent_fabric.adapters.langgraph_adapter import LangGraphAdapter
from agent_fabric.adapters.crewai_adapter import CrewAIAdapter


@pytest.fixture(autouse=True)
def mock_openai_environment():
    os.environ["OPENAI_API_KEY"] = "sk-test"
    settings.providers.openai_api_key = SecretStr("sk-test")
    with patch("agent_fabric.providers.openai.OPENAI_AVAILABLE", True), \
         patch("agent_fabric.providers.openai.AsyncOpenAI", create=True) as mock_client:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Mock OpenAI Response", tool_calls=[]))]))
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_provider():
    p = AsyncMock()
    p.default_model = "mock-sdk-model"
    p.chat.return_value = {"content": "SDK Phase B response", "tool_calls": []}
    return p


@pytest.mark.asyncio
async def test_sdk_phase_b_comprehensive(mock_provider):
    """Exhaustive Phase B testing of SDK, Runtime, Memory, Pipelines, Teams, and Adapters."""
    # 1. Agent Runtime & Provider Routing
    agent = Agent(name="sdk_agent", provider=mock_provider)
    res = await agent.run("Test SDK execution")
    assert res.text == "SDK Phase B response"

    # 2. Team Collaboration Strategies (Sequential, Parallel, Supervisor)
    seq_team = Team(agents=[Agent("a1", provider=mock_provider), Agent("a2", provider=mock_provider)], strategy="sequential")
    res_seq = await seq_team.run("Sequential Task")
    assert res_seq.text is not None

    par_team = Team(agents=[Agent("p1", provider=mock_provider), Agent("p2", provider=mock_provider)], strategy="parallel")
    res_par = await par_team.run("Parallel Task")
    assert res_par.text is not None

    sup_team = Team(agents=[Agent("s1", provider=mock_provider), Agent("s2", provider=mock_provider)], strategy="supervisor")
    res_sup = await sup_team.run("Supervisor Task")
    assert res_sup.text is not None

    # 3. Pipeline DAG Execution & Context Interpolation
    pipe = Pipeline(
        id="pipe-sdk",
        name="SDK Pipeline",
        nodes=[
            PipelineNode(id="step1", type="transform", config={"template": "Hello SDK"}),
            PipelineNode(id="step2", type="transform", depends_on=["step1"], config={"template": "Echo: ${step1.output}"})
        ]
    )
    executor = PipelineExecutor(pipe)
    run_rec = await executor.run()
    assert run_rec.outputs["step2"] == "Echo: Hello SDK"

    # 4. Scheduler Engine Operations
    engine = SchedulerEngine()
    sched = Schedule(name="sdk_sched", trigger_type="cron", trigger_config={"cron_expression": "0 * * * *"}, target_type="agent", target_name="sdk_agent")
    engine.create_schedule(sched)
    assert len(engine.list_schedules()) >= 1
    engine.delete_schedule(sched.id)

    # 5. Advanced Memory & Knowledge Graph
    store = SQLiteMemoryStore()
    consolidator = MemoryConsolidator(store=store)
    cons_rec = await consolidator.consolidate()
    assert cons_rec.text is not None

    forgetting = ForgettingPolicy(store=store, max_capacity=10)
    purged = await forgetting.apply_capacity_policy()
    assert isinstance(purged, int)

    kg = KnowledgeGraph()
    kg.add_node("k1", "entity", "Ent1")
    kg.add_node("k2", "entity", "Ent2")
    kg.add_edge("k1", "k2", "LINKED")
    assert kg.find_path("k1", "k2") == ["k1", "k2"]

    g_id = await shared_memory.store_global("SDK Global Pref")
    assert g_id is not None

    # 6. Adapters (Generic BYOA, LangGraph, CrewAI)
    class RawBot:
        def run(self, msg: str) -> str:
            return f"RawBot: {msg}"
    gen_adapter = GenericAgentAdapter(target_agent=RawBot(), name="raw_bot", memory=False, observe=False)
    res_gen = await gen_adapter.run("Test BYOA")
    assert "RawBot:" in res_gen.text

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = "Graph response"
    lg_adapter = LangGraphAdapter(graph_instance=mock_graph, agent_name="test_lg")
    res_lg = await lg_adapter.run("Run graph")
    assert "Graph response" in res_lg.text

    mock_crew = MagicMock()
    mock_crew.kickoff.return_value = "Crew response"
    crew_adapter = CrewAIAdapter(crew_instance=mock_crew, crew_name="test_crew")
    res_crew = await crew_adapter.run("Run crew")
    assert "Crew response" in res_crew.text
