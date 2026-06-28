"""
AgentFabric Memory Engine.
Provides structured SQLite storage, FTS5 full-text search, Knowledge Graph, consolidation, and shared memory.
"""
from agent_fabric.memory.engine import memory_engine as memory_engine, graph as graph, store as store, search as search, list_records as list_records, delete as delete, MemoryEngine as MemoryEngine
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore as SQLiteMemoryStore
from agent_fabric.memory.fts_search import SQLiteFTSSearcher as SQLiteFTSSearcher
from agent_fabric.memory.knowledge_graph import KnowledgeGraph as KnowledgeGraph
from agent_fabric.memory.consolidation import MemoryConsolidator as MemoryConsolidator
from agent_fabric.memory.forgetting import ForgettingPolicy as ForgettingPolicy
from agent_fabric.memory.shared import SharedMemoryPool as SharedMemoryPool, shared_memory as shared_memory

__all__ = [
    "memory_engine",
    "graph",
    "store",
    "search",
    "list_records",
    "delete",
    "MemoryEngine",
    "SQLiteMemoryStore",
    "SQLiteFTSSearcher",
    "KnowledgeGraph",
    "MemoryConsolidator",
    "ForgettingPolicy",
    "SharedMemoryPool",
    "shared_memory"
]
