import os
import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock, AsyncMock
from agent_fabric.core.config import settings
from agent_fabric.core.models import Event
from agent_fabric.core.events import event_bus
from agent_fabric.core.workspace import Workspace
from agent_fabric.runtime.agent import Agent, AgentResult
from agent_fabric.runtime.enhance import enhance
from agent_fabric.runtime.runtime import Runtime
from agent_fabric.observability.event_store import event_store
from agent_fabric.providers.openai import OpenAIProvider
from agent_fabric.providers.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_event_store_persistence():
    """Verify that EventBus events are automatically persisted to the SQLite EventStore."""
    with TemporaryDirectory() as temp_dir:
        old_dir = settings.agentfabric_dir
        settings.agentfabric_dir = Path(temp_dir)
        
        try:
            # Re-initialize event store table under the new directory path
            event_store._ensure_table()
            
            # 1. Publish test events
            e1 = Event(event_type="AgentStarted", actor="agent:test", data={"task": "do work"})
            e2 = Event(event_type="ToolInvoked", actor="agent:test", data={"tool": "search"})
            
            await event_bus.publish(e1)
            await event_bus.publish(e2)
            
            # Allow async handlers to run (gathered in publish, so it runs immediately)
            # 2. Query EventStore
            events = event_store.query()
            assert len(events) >= 2
            
            types = [e.event_type for e in events]
            assert "AgentStarted" in types
            assert "ToolInvoked" in types
            
        finally:
            settings.agentfabric_dir = old_dir


@pytest.mark.asyncio
@patch("agent_fabric.providers.openai.OPENAI_AVAILABLE", True)
@patch("agent_fabric.providers.openai.AsyncOpenAI", create=True)
async def test_openai_provider(mock_openai_class):
    """Test that OpenAIProvider formats requests and parses responses correctly."""
    # Mock AsyncOpenAI client
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    # Mock completions create response
    func_mock = MagicMock()
    func_mock.name = "web_search"
    func_mock.arguments = '{"query": "AgentFabric"}'
    
    tc_mock = MagicMock()
    tc_mock.id = "call_1"
    tc_mock.function = func_mock
    
    mock_choices = [
        MagicMock(
            message=MagicMock(
                content="Response from OpenAI",
                tool_calls=[tc_mock]
            )
        )
    ]
    mock_response = MagicMock(choices=mock_choices)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    # Instantiate provider
    provider = OpenAIProvider(api_key="test-key")
    
    # Run chat
    res = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"name": "web_search", "parameters": {}}]
    )
    
    assert res["content"] == "Response from OpenAI"
    assert len(res["tool_calls"]) == 1
    assert res["tool_calls"][0]["name"] == "web_search"
    assert res["tool_calls"][0]["arguments"] == {"query": "AgentFabric"}


@pytest.mark.asyncio
async def test_agent_execution_loop():
    """Verify that Agent executes LLM calls, handles tool loops, and persists output to memory."""
    with TemporaryDirectory() as temp_dir:
        old_dir = settings.agentfabric_dir
        settings.agentfabric_dir = Path(temp_dir)
        
        try:
            # Setup a mock LLM Provider
            mock_provider = AsyncMock()
            mock_provider.default_model = "mock-model"
            
            # Ensure event_store has its tables created in the temp db
            event_store._ensure_table()
            
            # Loop 1: returns tool call to "calculator"
            # Loop 2: returns final response content
            mock_provider.chat.side_effect = [
                {
                    "content": "Let me calculate.",
                    "tool_calls": [{"id": "call_1", "name": "calculator", "arguments": {"x": 5, "y": 3}}]
                },
                {
                    "content": "The sum is 8.",
                    "tool_calls": []
                }
            ]
            
            # Setup mock calculator tool
            mock_tool = AsyncMock()
            mock_tool.name = "calculator"
            mock_tool.description = "Add two numbers"
            mock_tool.parameters = {}
            mock_tool.execute = AsyncMock(return_value="8")
            
            # Instantiate agent
            agent = Agent(
                name="math_bot",
                provider=mock_provider,
                tools=[mock_tool]
            )
            
            # Run agent
            result = await agent.run("What is 5 + 3?")
            
            assert result.text == "The sum is 8."
            assert len(result.messages) == 5  # System, User, Assistant(tool_call), Tool(result), Assistant(final)
            
            # Check logs
            logs = agent.logs()
            assert len(logs) > 0
            
            # Clean up logger handlers to unlock the log file under Windows
            for handler in agent.logger.handlers:
                handler.close()
            agent.logger.handlers.clear()
            
        finally:
            settings.agentfabric_dir = old_dir


@pytest.mark.asyncio
async def test_enhance_byoa_wrapper():
    """Verify that enhance() wraps classes, intercepts calls, and injects memory context."""
    with TemporaryDirectory() as temp_dir:
        old_dir = settings.agentfabric_dir
        settings.agentfabric_dir = Path(temp_dir)
        
        try:
            # Ensure event_store has its tables created in the temp db
            event_store._ensure_table()
            
            # 1. Store a memory we expect to be retrieved
            from agent_fabric.memory.engine import memory_engine
            await memory_engine.store(
                text="The secret code is 12345.",
                tags=["secrets"]
            )
            
            # 2. Define a simple target agent class representing a third-party agent
            class CustomAgent:
                async def run(self, task: str) -> str:
                    return f"Executed: {task}"
                    
            # Enhance it!
            legacy_agent = CustomAgent()
            enhanced_agent = enhance(legacy_agent, memory=True, observe=True)
            
            # Verify class wrapping proxy
            assert enhanced_agent._name == "CustomAgent"
            
            # Execute enhanced method
            res = await enhanced_agent.run(task="Give me the secret code.")
            
            # Check that context memory was injected into prompt argument
            assert "Executed:" in res
            assert "[CONTEXT MEMORY]" in res
            assert "The secret code is 12345." in res
            
            # Verify output auto-stored to memory
            mems = await memory_engine.list_records()
            texts = [m.text for m in mems]
            assert any("Result: Executed:" in t for t in texts)
            
        finally:
            settings.agentfabric_dir = old_dir
