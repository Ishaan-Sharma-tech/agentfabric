import os
import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from agent_fabric.core.models import MemoryRecord
from agent_fabric.core.permissions import Capability, AgentFabricPermissionError
from agent_fabric.core.events import event_bus
from agent_fabric.core.config import settings
from agent_fabric.core.workspace import Workspace
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore
from agent_fabric.memory.fts_search import SQLiteFTSSearcher
from agent_fabric.memory.knowledge_graph import KnowledgeGraph
from agent_fabric.memory.engine import MemoryEngine
from agent_fabric.tools.decorator import tool
from agent_fabric.tools.registry import tool_registry
from agent_fabric.tools.runtime import ToolExecutor


@pytest.mark.asyncio
async def test_memory_engine_and_fts():
    """Verify that MemoryEngine can store, FTS search, and delete memories."""
    with TemporaryDirectory() as temp_dir:
        old_dir = settings.agentfabric_dir
        settings.agentfabric_dir = Path(temp_dir)
        
        try:
            engine = MemoryEngine()
            
            # 1. Store a memory
            m1_id = await engine.store(
                text="AgentFabric provides a capability-based security model.",
                tags=["security", "kernel"],
                metadata={"version": "1.0"}
            )
            
            # 2. Store another memory
            m2_id = await engine.store(
                text="The SQLite database contains adjacency tables for the Knowledge Graph.",
                tags=["graph", "sqlite"]
            )
            
            # 3. Test FTS5 Search
            results = await engine.search("security model")
            assert len(results) >= 1
            assert results[0].id == m1_id
            assert "capability-based" in results[0].text
            
            # 4. Test Search with filters
            filtered_results = await engine.search("security model", filters={"tag": "security"})
            assert len(filtered_results) == 1
            
            mismatch_filter = await engine.search("security model", filters={"tag": "graph"})
            assert len(mismatch_filter) == 0

            # 5. List memories
            all_mems = await engine.list_records()
            assert len(all_mems) == 2

            # 6. Delete a memory
            await engine.delete(m1_id)
            results_after_delete = await engine.search("security model")
            assert len(results_after_delete) == 0
            
        finally:
            settings.agentfabric_dir = old_dir


def test_knowledge_graph():
    """Verify nodes, edges, neighbors, and shortest path traversal in the Knowledge Graph."""
    with TemporaryDirectory() as temp_dir:
        old_dir = settings.agentfabric_dir
        settings.agentfabric_dir = Path(temp_dir)
        
        try:
            graph = KnowledgeGraph()
            
            # 1. Add nodes
            graph.add_node("A", "User", "Alice")
            graph.add_node("B", "Framework", "AgentFabric")
            graph.add_node("C", "Language", "Python")
            graph.add_node("D", "Library", "Pydantic")
            
            # Verify node retrieval
            node_a = graph.get_node("A")
            assert node_a is not None
            assert node_a["name"] == "Alice"
            
            # 2. Add edges
            graph.add_edge("A", "B", "USES")
            graph.add_edge("B", "C", "WRITTEN_IN")
            graph.add_edge("C", "D", "DEPENDS_ON")
            
            # 3. Test neighbors
            neighbors_b = graph.neighbors("B")
            # Should have outgoing to C and incoming from A
            neighbor_ids = [n["id"] for n in neighbors_b]
            assert "C" in neighbor_ids
            assert "A" in neighbor_ids
            
            # 4. Test shortest path (A -> B -> C -> D)
            path_a_d = graph.path("A", "D")
            assert path_a_d == ["A", "B", "C", "D"]
            
            # Test non-existent path
            graph.add_node("X", "Unconnected", "Unknown")
            path_a_x = graph.path("A", "X")
            assert path_a_x is None
            
        finally:
            settings.agentfabric_dir = old_dir


def test_tool_decorator_and_schema():
    """Verify that @tool decorator extracts metadata and Pydantic schemas properly."""
    tool_registry.clear()
    
    @tool(name="sum_numbers", description="Add two integers together.")
    def add(x: int, y: int = 10) -> int:
        """This function adds x and y."""
        return x + y
        
    assert add.name == "sum_numbers"
    assert add.description == "Add two integers together."
    
    # Check parameters JSON schema
    schema = add.parameters
    assert schema["type"] == "object"
    assert "x" in schema["properties"]
    assert "y" in schema["properties"]
    assert schema["properties"]["x"]["type"] == "integer"
    assert "x" in schema["required"]
    assert "y" not in schema.get("required", [])


@pytest.mark.asyncio
async def test_tool_executor_and_permissions():
    """Verify tool execution, permission gating, and EventBus integration."""
    tool_registry.clear()
    
    # Define a dummy tool
    @tool
    def divide(a: float, b: float) -> float:
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero.")
        return a / b

    # Create executor with specific capability
    cap_allow = [Capability(resource="tool", action="execute", scope="divide")]
    executor = ToolExecutor("math_agent", cap_allow)
    
    # 1. Verify successful execution
    result = await executor.execute("divide", {"a": 10.0, "b": 2.0})
    assert float(result) == 5.0

    # 2. Verify permission failure
    cap_deny = [Capability(resource="tool", action="execute", scope="other_tool")]
    unauthorized_executor = ToolExecutor("math_agent", cap_deny)
    
    with pytest.raises(AgentFabricPermissionError):
        await unauthorized_executor.execute("divide", {"a": 10.0, "b": 2.0})

    # 3. Verify event bus propagation
    invoked_events = []
    result_events = []
    
    async def on_invoke(event):
        invoked_events.append(event)
    async def on_result(event):
        result_events.append(event)
        
    event_bus.subscribe("ToolInvoked", on_invoke)
    event_bus.subscribe("ToolResult", on_result)
    
    await executor.execute("divide", {"a": 4.0, "b": 2.0})
    
    # Check that events were captured
    assert len(invoked_events) == 1
    assert invoked_events[0].data["tool_name"] == "divide"
    assert len(result_events) == 1
    assert result_events[0].data["tool_name"] == "divide"
    assert float(result_events[0].data["result"]) == 2.0


def test_file_ops_tools(tmp_path):
    """Verify local file read/write operations."""
    test_file = tmp_path / "test.txt"
    content = "Hello, AgentFabric!"
    
    # Test write tool
    from agent_fabric.tools.builtin.file_ops import write_file, read_file
    
    write_res = write_file(path=str(test_file), content=content)
    assert "Successfully wrote" in write_res
    assert test_file.read_text() == content
    
    # Test read tool
    read_res = read_file(path=str(test_file))
    assert read_res == content


@patch("urllib.request.urlopen")
def test_url_reader_mocked(mock_urlopen):
    """Verify url_reader handles text extraction and page parsing correctly."""
    # Mock response
    mock_response = MagicMock()
    mock_response.info.return_value.get_content_type.return_value = "text/html"
    mock_response.read.return_value = b"""
    <html>
        <head><title>Test Page</title></head>
        <body>
            <script>console.log('strip me');</script>
            <style>body { background: red; }</style>
            <h1>AgentFabric Kernel</h1>
            <p>This is a zero-config agent runtime.</p>
        </body>
    </html>
    """
    mock_urlopen.return_value.__enter__.return_value = mock_response

    from agent_fabric.tools.builtin.url_reader import url_reader
    
    res = url_reader("https://example.com/test")
    # Verify that tags, scripts, and styles are stripped
    assert "AgentFabric Kernel" in res
    assert "console.log" not in res
    assert "background: red" not in res
    assert "html" not in res
