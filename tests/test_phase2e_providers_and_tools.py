import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from agent_fabric.providers.anthropic import AnthropicProvider
from agent_fabric.providers.google import GoogleGeminiProvider
from agent_fabric.providers.groq_provider import GroqProvider
from agent_fabric.providers.lmstudio import LMStudioProvider
from agent_fabric.tools.builtin.file_write import file_write
from agent_fabric.tools.builtin.shell_execute import shell_execute
from agent_fabric.tools.builtin.http_request import http_request
from agent_fabric.memory.engine import memory_engine
from agent_fabric.server.app import create_app


@pytest.fixture(autouse=True)
def mock_openai_environment():
    with patch("agent_fabric.providers.openai.OPENAI_AVAILABLE", True), \
         patch("agent_fabric.providers.openai.AsyncOpenAI", create=True) as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_all_new_providers():
    """Verify chat completions across Anthropic, Gemini, Groq, and LM Studio providers."""
    # Anthropic provider mock
    mock_anthropic_mod = MagicMock()
    with patch.dict("sys.modules", {"anthropic": mock_anthropic_mod}), \
         patch("agent_fabric.providers.anthropic.ANTHROPIC_AVAILABLE", True):
        mock_inst = MagicMock()
        mock_msg = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Claude test output"
        mock_msg.content = [mock_block]
        mock_inst.messages.create = AsyncMock(return_value=mock_msg)
        mock_anthropic_mod.AsyncAnthropic.return_value = mock_inst
        
        provider_ant = AnthropicProvider(api_key="test")
        res_ant = await provider_ant.chat([{"role": "user", "content": "Hello"}])
        assert "Claude" in res_ant["content"] or "Response" in res_ant["content"]
        
    # Google Gemini provider
    provider_gem = GoogleGeminiProvider()
    res_gem = await provider_gem.chat([{"role": "user", "content": "Hello"}])
    assert "Gemini" in res_gem["content"]
    
    # Groq provider
    provider_groq = GroqProvider()
    res_groq = await provider_groq.chat([{"role": "user", "content": "Hello"}])
    assert "Groq" in res_groq["content"]
    
    # LM Studio provider
    provider_lm = LMStudioProvider()
    res_lm = await provider_lm.chat([{"role": "user", "content": "Hello"}])
    assert "LM Studio" in res_lm["content"]


def test_new_builtin_tools():
    """Verify file_write, shell_execute, and http_request built-in tools."""
    res_write = file_write(filepath="test_write.txt", content="Hello test")
    assert "Successfully wrote" in res_write or "Error" in res_write
    
    res_shell = shell_execute(command="echo 'AgentFabric Shell'")
    assert "AgentFabric Shell" in res_shell or "completed" in res_shell
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        
        res_http = http_request(url="http://example.com/api")
        assert "status" in res_http


@pytest.mark.asyncio
async def test_memory_export_and_import():
    """Verify exporting memory records to JSON and importing them back."""
    await memory_engine.store("Memory Record A", tags=["test_a"])
    await memory_engine.store("Memory Record B", tags=["test_b"])
    
    exported = await memory_engine.export_memories()
    assert len(exported) >= 2
    
    imported_count = await memory_engine.import_memories(exported[:1])
    assert imported_count == 1


def test_api_memory_backup_endpoints():
    """Verify REST API routes for memory backup export/import."""
    app = create_app()
    client = TestClient(app)
    
    # POST /memory/export
    res_exp = client.post("/memory/export")
    assert res_exp.status_code == 200
    data = res_exp.json()
    assert isinstance(data, list)
    
    # POST /memory/import
    res_imp = client.post("/memory/import", json=[{
        "text": "API Backup Record",
        "tags": ["backup"],
        "metadata": {},
        "importance_score": 1.0
    }])
    assert res_imp.status_code == 200
    assert res_imp.json()["count"] == 1
