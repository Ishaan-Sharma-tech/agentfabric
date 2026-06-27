import re
import asyncio
from typing import List, Optional, Dict, Any
from agent_fabric.memory.sqlite_store import get_db_conn, SQLiteMemoryStore
from agent_fabric.core.models import MemoryRecord

__all__ = ["SQLiteFTSSearcher"]


class SQLiteFTSSearcher:
    """
    Implements FTS5 full-text search against the memories SQLite database.
    Zero-config and zero external dependencies.
    """
    def __init__(self, store: Optional[SQLiteMemoryStore] = None):
        self.store = store or SQLiteMemoryStore()

    def _search_sync(
        self, 
        query: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        if not query.strip():
            return []

        clean_limit = max(1, min(limit, 100))
        matching_ids: List[str] = []
        
        with get_db_conn() as conn:
            cursor = conn.cursor()
            try:
                words = re.findall(r'\w+', query)[:20]
                fts_query = " OR ".join(words) if words else query
                
                # Fetch candidate IDs with buffer for filtering
                fetch_limit = clean_limit * 3 if filters else clean_limit
                cursor.execute(
                    "SELECT id FROM memories_fts WHERE text MATCH ? ORDER BY rank LIMIT ?",
                    (fts_query, fetch_limit)
                )
                matching_ids = [row["id"] for row in cursor.fetchall()]
            except Exception:
                # Escape LIKE wildcards
                escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                query_like = f"%{escaped_query}%"
                fetch_limit = clean_limit * 3 if filters else clean_limit
                cursor.execute(
                    "SELECT id FROM memories WHERE text LIKE ? ESCAPE '\\' ORDER BY created_at DESC LIMIT ?",
                    (query_like, fetch_limit)
                )
                matching_ids = [row["id"] for row in cursor.fetchall()]

        results: List[MemoryRecord] = []
        if not matching_ids:
            return results

        with get_db_conn() as conn:
            placeholders = ",".join(["?"] * len(matching_ids))
            sql = f"SELECT * FROM memories WHERE id IN ({placeholders})"
            cursor = conn.cursor()
            cursor.execute(sql, tuple(matching_ids))
            record_map = {row["id"]: self.store._row_to_record(row) for row in cursor.fetchall()}

        for record_id in matching_ids:
            record = record_map.get(record_id)
            if record:
                if filters:
                    if "agent_id" in filters and record.agent_id != filters["agent_id"]:
                        continue
                    if "tag" in filters and filters["tag"] not in record.tags:
                        continue
                results.append(record)
                if len(results) >= clean_limit:
                    break

        return results

    async def search(
        self, 
        query: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """Async FTS search matching MemoryBackend protocol."""
        return await asyncio.to_thread(self._search_sync, query, limit, filters)

