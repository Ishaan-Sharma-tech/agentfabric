import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator
from agent_fabric.core.workspace import Workspace
from agent_fabric.core.models import MemoryRecord


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize the SQLite database schema if not already initialized."""
    cursor = conn.cursor()
    
    # 1. Memories Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        tags TEXT, -- JSON array of strings
        metadata TEXT, -- JSON object
        agent_id TEXT,
        created_at TEXT NOT NULL,
        accessed_at TEXT NOT NULL,
        importance_score REAL NOT NULL
    )
    """)
    
    # 2. Memories FTS5 Virtual Table (zero external dependencies full text search)
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
        id UNINDEXED,
        text
    )
    """)
    
    # 3. Knowledge Graph Nodes Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS graph_nodes (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        name TEXT NOT NULL,
        properties TEXT -- JSON object
    )
    """)
    
    # 4. Knowledge Graph Edges Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS graph_edges (
        source TEXT NOT NULL,
        target TEXT NOT NULL,
        relationship TEXT NOT NULL,
        properties TEXT, -- JSON object
        PRIMARY KEY (source, target, relationship),
        FOREIGN KEY (source) REFERENCES graph_nodes(id) ON DELETE CASCADE,
        FOREIGN KEY (target) REFERENCES graph_nodes(id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()


@contextmanager
def get_db_conn() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager to obtain a database connection for the current active workspace.
    Ensures workspace directories and database schemas are initialized.
    """
    workspace = Workspace.current()
    workspace.ensure_exists()
    
    conn = sqlite3.connect(workspace.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Initialize DB schema
    init_db(conn)
    
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class SQLiteMemoryStore:
    """
    Handles persistence of MemoryRecord instances to SQLite and FTS5 index.
    """
    
    def store(self, record: MemoryRecord) -> None:
        """Insert or update a memory record in both the main table and FTS5 index."""
        record_dict = record.model_dump()
        
        with get_db_conn() as conn:
            cursor = conn.cursor()
            
            # Serialize fields for SQLite
            tags_json = json.dumps(record_dict["tags"])
            meta_json = json.dumps(record_dict["metadata"])
            created_str = record_dict["created_at"].isoformat()
            accessed_str = record_dict["accessed_at"].isoformat()
            
            # Check if record already exists to perform update or insert
            cursor.execute("SELECT 1 FROM memories WHERE id = ?", (record.id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update main table
                cursor.execute("""
                UPDATE memories 
                SET text = ?, tags = ?, metadata = ?, agent_id = ?, accessed_at = ?, importance_score = ?
                WHERE id = ?
                """, (
                    record.text, 
                    tags_json, 
                    meta_json, 
                    record.agent_id, 
                    accessed_str, 
                    record.importance_score, 
                    record.id
                ))
                # Update FTS table (delete then insert)
                cursor.execute("DELETE FROM memories_fts WHERE id = ?", (record.id,))
                cursor.execute("INSERT INTO memories_fts (id, text) VALUES (?, ?)", (record.id, record.text))
            else:
                # Insert main table
                cursor.execute("""
                INSERT INTO memories (id, text, tags, metadata, agent_id, created_at, accessed_at, importance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id, 
                    record.text, 
                    tags_json, 
                    meta_json, 
                    record.agent_id, 
                    created_str, 
                    accessed_str, 
                    record.importance_score
                ))
                # Insert FTS table
                cursor.execute("INSERT INTO memories_fts (id, text) VALUES (?, ?)", (record.id, record.text))

    def delete(self, record_id: str) -> None:
        """Delete a memory record from both tables by ID."""
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (record_id,))
            cursor.execute("DELETE FROM memories_fts WHERE id = ?", (record_id,))

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a memory record by ID."""
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memories WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_all(self, limit: int = 100, filters: Optional[Dict[str, Any]] = None) -> List[MemoryRecord]:
        """List memory records with optional filters (e.g. tag, agent_id)."""
        query = "SELECT * FROM memories"
        params: List[Any] = []
        where_clauses: List[str] = []
        
        if filters:
            if "agent_id" in filters:
                where_clauses.append("agent_id = ?")
                params.append(filters["agent_id"])
            if "tag" in filters:
                # Tag exists inside the JSON array (SQLite JSON function)
                where_clauses.append("exists (select 1 from json_each(tags) where value = ?)")
                params.append(filters["tag"])
                
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        """Helper to map a SQLite Row to a MemoryRecord Pydantic model."""
        return MemoryRecord(
            id=row["id"],
            text=row["text"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            agent_id=row["agent_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            accessed_at=datetime.fromisoformat(row["accessed_at"]),
            importance_score=row["importance_score"]
        )
