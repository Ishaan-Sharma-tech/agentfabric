import logging
from typing import List, Optional, Dict, Any
from agent_fabric.core.config import settings
from agent_fabric.core.models import MemoryRecord
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore
from agent_fabric.memory.fts_search import SQLiteFTSSearcher
from agent_fabric.memory.knowledge_graph import KnowledgeGraph

logger = logging.getLogger("agent_fabric.memory.engine")

__all__ = ["MemoryEngine", "memory_engine", "graph", "store", "search", "list_records", "delete"]


class MemoryEngine:
    """
    Facade coordinating the memory storage engine.
    Wraps SQLite/FTS5 and optional Qdrant vector backends into a unified async API.
    """
    def __init__(self) -> None:
        self.sqlite_store = SQLiteMemoryStore()
        self.fts_searcher = SQLiteFTSSearcher(self.sqlite_store)
        self._vector_store: Any = None
        self.graph = KnowledgeGraph()

    def _get_active_backend(self) -> Any:
        """Dynamically resolve the configured backend."""
        if settings.memory_backend in ("vector", "qdrant"):
            if self._vector_store is None:
                from agent_fabric.memory.vector_store import QdrantVectorStore
                vector_path = str(settings.agentfabric_dir / "workspaces" / settings.current_workspace / "qdrant_db")
                self._vector_store = QdrantVectorStore(location=vector_path)
            return self._vector_store
        return self.sqlite_store

    async def store(
        self, 
        text: str, 
        tags: Optional[List[str]] = None, 
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        importance_score: float = 1.0
    ) -> str:
        """
        Store a memory string. Automatically generates a MemoryRecord,
        indexes it in SQLite FTS5, and optionally upserts to the vector store.
        """
        record = MemoryRecord(
            text=text,
            tags=tags or [],
            metadata=metadata or {},
            agent_id=agent_id,
            importance_score=importance_score
        )
        
        await self.sqlite_store.store(record)
        
        backend = self._get_active_backend()
        if backend is not self.sqlite_store:
            try:
                await backend.store(record)
            except Exception as e:
                logger.warning(f"Failed to store record in vector backend: {e}", exc_info=True)
            
        return record.id

    async def search(
        self, 
        query: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """
        Search memories. Uses semantic vector search if vector store is active,
        falling back to high-performance local SQLite FTS5 full-text search.
        """
        backend = self._get_active_backend()
        if backend is not self.sqlite_store:
            try:
                return await backend.search(query, limit, filters)
            except Exception as e:
                logger.warning(f"Vector search failed; falling back to FTS5 search: {e}", exc_info=True)
                
        return await self.fts_searcher.search(query, limit, filters)

    async def list_records(
        self, 
        limit: int = 100, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """List stored memories under the active workspace."""
        backend = self._get_active_backend()
        if backend is not self.sqlite_store:
            try:
                return await backend.list_records(limit, filters)
            except Exception as e:
                logger.warning(f"Vector backend list_records failed; falling back to SQLite: {e}", exc_info=True)
        return await self.sqlite_store.list_all(limit, filters)

    async def delete(self, record_id: str) -> None:
        """Delete a memory record from active backends by ID."""
        await self.sqlite_store.delete(record_id)
        
        backend = self._get_active_backend()
        if backend is not self.sqlite_store:
            try:
                await backend.delete(record_id)
            except Exception as e:
                logger.warning(f"Vector backend delete failed for record '{record_id}': {e}", exc_info=True)

    async def export_memories(self) -> List[Dict[str, Any]]:
        """Export all memory records as a list of dictionaries for backup."""
        records = await self.list_records(limit=1000)
        return [r.model_dump() for r in records]

    async def import_memories(self, records_data: List[Dict[str, Any]]) -> int:
        """Import memory records from a list of dictionaries."""
        count = 0
        for data in records_data:
            rec = MemoryRecord(**data)
            await self.sqlite_store.store(rec)
            count += 1
        return count


# Global singleton facade
memory_engine = MemoryEngine()
graph = memory_engine.graph

# Top-level API shortcuts
async def store(
    text: str, 
    tags: Optional[List[str]] = None, 
    metadata: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    importance_score: float = 1.0
) -> str:
    return await memory_engine.store(text, tags, metadata, agent_id, importance_score)


async def search(
    query: str, 
    limit: int = 5, 
    filters: Optional[Dict[str, Any]] = None
) -> List[MemoryRecord]:
    return await memory_engine.search(query, limit, filters)


async def list_records(
    limit: int = 100, 
    filters: Optional[Dict[str, Any]] = None
) -> List[MemoryRecord]:
    return await memory_engine.list_records(limit, filters)


async def delete(record_id: str) -> None:
    await memory_engine.delete(record_id)

