import pytest
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore
from agent_fabric.memory.consolidation import MemoryConsolidator
from agent_fabric.memory.forgetting import ForgettingPolicy
from agent_fabric.memory.knowledge_graph import KnowledgeGraph
from agent_fabric.memory.shared import shared_memory
from agent_fabric.core.models import MemoryRecord


@pytest.mark.asyncio
async def test_memory_consolidation_and_forgetting():
    """Verify memory consolidation merging and capacity-based forgetting policies."""
    store = SQLiteMemoryStore()
    
    # Store multiple records
    for i in range(5):
        rec = MemoryRecord(text=f"Short term record {i}", tags=["agent_run"], importance_score=0.5 + i * 0.1)
        await store.store(rec)
        
    # Store pinned record
    pinned_rec = MemoryRecord(text="Pinned Record", tags=["agent_run"], metadata={"pinned": True}, importance_score=0.1)
    await store.store(pinned_rec)
    
    # Consolidate
    consolidator = MemoryConsolidator(store=store)
    cons_rec = await consolidator.consolidate(tag_filter="agent_run")
    assert "Consolidated" in cons_rec.text
    
    # Forgetting policy
    forgetting = ForgettingPolicy(store=store, max_capacity=3)
    purged_count = await forgetting.apply_capacity_policy()
    assert purged_count >= 1
    
    # Verify pinned record survived
    survived = await store.list_records(limit=100)
    assert any(r.id == pinned_rec.id for r in survived)


def test_knowledge_graph_multihop_and_subgraph():
    """Verify multi-hop path query finding and subgraph extraction."""
    kg = KnowledgeGraph()
    kg.add_node("node1", "concept", "Concept A")
    kg.add_node("node2", "concept", "Concept B")
    kg.add_node("node3", "concept", "Concept C")
    
    kg.add_edge("node1", "node2", "CONNECTS_TO")
    kg.add_edge("node2", "node3", "LEADS_TO")
    
    path = kg.find_path("node1", "node3")
    assert path == ["node1", "node2", "node3"]
    
    subgraph = kg.extract_subgraph("node1", depth=2)
    assert len(subgraph["nodes"]) >= 2
    assert len(subgraph["edges"]) >= 1


@pytest.mark.asyncio
async def test_shared_memory_pool():
    """Verify global cross-workspace memory pool."""
    rec_id = await shared_memory.store_global(text="User prefers dark mode", tags=["settings"])
    assert rec_id is not None
    
    globals_list = await shared_memory.list_global()
    assert len(globals_list) >= 1
    assert "dark mode" in globals_list[0].text
