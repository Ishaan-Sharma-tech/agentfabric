import logging
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore

logger = logging.getLogger("agent_fabric.memory.forgetting")

__all__ = ["ForgettingPolicy"]


class ForgettingPolicy:
    """
    Manages automated memory retention policies (capacity-based, time-based, relevance-based).
    Protects pinned records (metadata contains 'pinned': True).
    """
    def __init__(self, store: SQLiteMemoryStore, max_capacity: int = 1000) -> None:
        self.store = store
        self.max_capacity = max_capacity

    async def apply_capacity_policy(self) -> int:
        """Purges lowest importance unpinned records if total exceeds max_capacity."""
        records = await self.store.list_records(limit=2000)
        if len(records) <= self.max_capacity:
            return 0

        # Sort by importance_score ascending (lowest first)
        unpinned = [r for r in records if not r.metadata.get("pinned", False)]
        unpinned.sort(key=lambda r: r.importance_score)

        purge_count = len(records) - self.max_capacity
        purged = 0
        for r in unpinned[:purge_count]:
            await self.store.delete(r.id)
            purged += 1

        logger.info(f"Forgetting Policy: Purged {purged} low-importance memory records.")
        return purged
