import logging
from agent_fabric.core.models import MemoryRecord
from agent_fabric.memory.sqlite_store import SQLiteMemoryStore

logger = logging.getLogger("agent_fabric.memory.consolidation")

__all__ = ["MemoryConsolidator"]


class MemoryConsolidator:
    """
    Consolidates related short-term memory records into long-term summary memories.
    """
    def __init__(self, store: SQLiteMemoryStore) -> None:
        self.store = store

    async def consolidate(self, tag_filter: str = "agent_run") -> MemoryRecord:
        """Merges records matching tag_filter into a consolidated long-term summary record."""
        records = await self.store.list_records(limit=20, filters={"tag": tag_filter})
        if not records:
            summary_text = f"Consolidated Memory Summary ({tag_filter}): No recent records found."
            rec = MemoryRecord(text=summary_text, tags=["consolidated", tag_filter], importance_score=1.5)
            await self.store.store(rec)
            return rec

        combined_text = "\n".join(r.text for r in records[:5])
        summary_text = f"Consolidated Summary of {len(records[:5])} records:\n{combined_text[:500]}"
        consolidated_rec = MemoryRecord(
            text=summary_text,
            tags=["consolidated", tag_filter],
            metadata={"source_count": len(records[:5])},
            importance_score=2.0
        )
        await self.store.store(consolidated_rec)
        logger.info(f"Consolidated {len(records[:5])} memory records under tag '{tag_filter}'.")
        return consolidated_rec
