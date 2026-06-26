from typing import List, Optional, Dict, Any
from agent_fabric.memory.sqlite_store import get_db_conn, SQLiteMemoryStore
from agent_fabric.core.models import MemoryRecord


class SQLiteFTSSearcher:
    """
    Implements FTS5 full-text search against the memories SQLite database.
    Zero-config and zero external dependencies.
    """
    def __init__(self, store: Optional[SQLiteMemoryStore] = None):
        self.store = store or SQLiteMemoryStore()

    def search(
        self, 
        query: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """
        Search for memory records using SQLite FTS5 matching on the text column.
        FTS5 orders matching results by relevance (rank) by default.
        """
        if not query.strip():
            return []

        # 1. Fetch matching IDs from the FTS5 virtual table
        matching_ids: List[str] = []
        with get_db_conn() as conn:
            cursor = conn.cursor()
            try:
                import re
                # Extract alphanumeric words and join with OR to avoid strict phrase matching
                words = re.findall(r'\w+', query)
                fts_query = " OR ".join(words) if words else query
                
                # FTS5 MATCH query ordering by rank (relevance score)
                cursor.execute(
                    "SELECT id FROM memories_fts WHERE text MATCH ? ORDER BY rank LIMIT ?",
                    (fts_query, limit)
                )
                matching_ids = [row["id"] for row in cursor.fetchall()]
            except Exception:
                # Fallback to simple LIKE query if FTS syntax error (e.g. malformed terms)
                # Escape search query terms
                query_like = f"%{query}%"
                cursor.execute(
                    "SELECT id FROM memories WHERE text LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (query_like, limit)
                )
                matching_ids = [row["id"] for row in cursor.fetchall()]
        
        # 2. Retrieve the complete MemoryRecord objects for the matching IDs
        results: List[MemoryRecord] = []
        for record_id in matching_ids:
            record = self.store.get(record_id)
            if record:
                # Apply post-filtering if filters are specified
                if filters:
                    # Filter by agent_id
                    if "agent_id" in filters and record.agent_id != filters["agent_id"]:
                        continue
                    # Filter by tag
                    if "tag" in filters and filters["tag"] not in record.tags:
                        continue
                results.append(record)
                
        return results
