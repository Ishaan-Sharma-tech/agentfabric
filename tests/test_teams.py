import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from tempfile import TemporaryDirectory
from pathlib import Path
from fastapi.testclient import TestClient

from agent_fabric.core.config import settings
from agent_fabric.runtime.agent import Agent
from agent_fabric.runtime.mailbox import Mailbox, AgentMessage
from agent_fabric.runtime.team import Team, TeamResult, SequentialStrategy, ParallelStrategy, SupervisorStrategy
from agent_fabric.server.app import create_app

@pytest.fixture(autouse=True)
def mock_openai_environment():
    with patch("agent_fabric.providers.openai.OPENAI_AVAILABLE", True), \
         patch("agent_fabric.providers.openai.AsyncOpenAI", create=True) as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_mailbox_messaging():
    """Verify asynchronous mailbox message publishing and receiving."""
    mb_alice = Mailbox("alice")
    mb_bob = Mailbox("bob")
    
    mb_alice.start()
    mb_bob.start()
    
    try:
        # Alice sends message to Bob
        await mb_alice.send(recipient="bob", message_type="task", content="Hello Bob!")
        
        # Bob receives message
        msg = await mb_bob.receive(timeout=2.0)
        assert msg.sender == "alice"
        assert msg.recipient == "bob"
        assert msg.content == "Hello Bob!"
    finally:
        mb_alice.stop()
        mb_bob.stop()


def test_agent_and_team_yaml_declarative():
    """Verify loading Agents and Teams from YAML configurations."""
    agent_yaml = """
name: analyst
system_prompt: Analyze data.
provider: ollama
model: llama3
"""
    agent = Agent.from_yaml(agent_yaml)
    assert agent.name == "analyst"
    assert agent.system_prompt == "Analyze data."

    team_yaml = """
name: research_team
strategy: parallel
agents:
  - name: researcher
    system_prompt: Gather facts.
    provider: ollama
  - name: writer
    system_prompt: Write report.
    provider: ollama
"""
    team = Team.from_yaml(team_yaml)
    assert team.name == "research_team"
    assert len(team.agents) == 2
    assert team.agents[0].name == "researcher"
    assert team.agents[1].name == "writer"
    assert isinstance(team.strategy, ParallelStrategy)


@pytest.mark.asyncio
async def test_sequential_strategy():
    """Verify SequentialStrategy chains outputs across agents."""
    a1 = Agent(name="step1", provider="ollama")
    a2 = Agent(name="step2", provider="ollama")
    
    with patch.object(a1.provider, "chat", new_callable=AsyncMock) as mock1, \
         patch.object(a2.provider, "chat", new_callable=AsyncMock) as mock2:
        mock1.return_value = {"role": "assistant", "content": "Step 1 complete", "tool_calls": []}
        mock2.return_value = {"role": "assistant", "content": "Step 2 complete", "tool_calls": []}
        
        team = Team(agents=[a1, a2], strategy="sequential")
        res = await team.run("Initial task")
        
        assert res.text == "Step 2 complete"
        assert res.outputs["step1"] == "Step 1 complete"
        assert res.outputs["step2"] == "Step 2 complete"


@pytest.mark.asyncio
async def test_parallel_strategy():
    """Verify ParallelStrategy executes agents concurrently."""
    a1 = Agent(name="worker1", provider="ollama")
    a2 = Agent(name="worker2", provider="ollama")
    
    with patch.object(a1.provider, "chat", new_callable=AsyncMock) as mock1, \
         patch.object(a2.provider, "chat", new_callable=AsyncMock) as mock2:
        mock1.return_value = {"role": "assistant", "content": "Worker 1 output", "tool_calls": []}
        mock2.return_value = {"role": "assistant", "content": "Worker 2 output", "tool_calls": []}
        
        team = Team(agents=[a1, a2], strategy="parallel")
        res = await team.run("Parallel task")
        
        assert "Worker 1 output" in res.text
        assert "Worker 2 output" in res.text
        assert res.outputs["worker1"] == "Worker 1 output"
        assert res.outputs["worker2"] == "Worker 2 output"


@pytest.mark.asyncio
async def test_supervisor_strategy():
    """Verify SupervisorStrategy equips supervisor with worker tool calls."""
    worker = Agent(name="worker", provider="ollama")
    supervisor = Agent(name="boss", provider="ollama")
    
    with patch.object(supervisor.provider, "chat", new_callable=AsyncMock) as mock_sup:
        mock_sup.return_value = {"role": "assistant", "content": "Boss delegated and consolidated.", "tool_calls": []}
        
        team = Team(agents=[worker], strategy="supervisor", supervisor=supervisor)
        res = await team.run("Complex orchestration task")
        
        assert res.text == "Boss delegated and consolidated."
        assert "supervisor" in res.outputs


def test_api_team_run_endpoint():
    """Verify POST /teams/run REST endpoint."""
    app = create_app()
    client = TestClient(app)
    
    with patch("agent_fabric.providers.ollama.OllamaProvider.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"role": "assistant", "content": "API Team Output", "tool_calls": []}
        
        response = client.post("/teams/run", json={
            "task": "Test API Team Task",
            "team_name": "api_team",
            "strategy": "sequential",
            "agents": [
                {"name": "agent1", "system_prompt": "First agent", "provider": "ollama"},
                {"name": "agent2", "system_prompt": "Second agent", "provider": "ollama"}
            ]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "API Team Output"
        assert "agent1" in data["outputs"]
        assert "agent2" in data["outputs"]
