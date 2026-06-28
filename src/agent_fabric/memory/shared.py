import logging
from typing import List, Dict, Any, Optional
from agent_fabric.core.models import MemoryRecord
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore

logger = logging.getLogger("agent_fabric.memory.shared")

__all__ = ["SharedMemoryPool", "shared_memory"]


class SharedMemoryPool:
    """
    Cross-workspace shared memory pool for global user preferences, contacts, and universal knowledge.
    """
    def __init__(self) -> None:
        self.store = SQLiteMemoryStore()

    async def store_global(self, text: str, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Stores a global memory accessible across workspaces."""
        g_tags = (tags or []) + ["global_shared"]
        record = MemoryRecord(text=text, tags=g_tags, metadata=metadata or {}, importance_score=2.0)
        await self.store.store(record)
        return record.id

    async def list_global(self) -> List[MemoryRecord]:
        """Lists global shared memory records."""
        return await self.store.list_records(limit=500, filters={"tag": "global_shared"})


shared_memory = SharedMemoryPool()
