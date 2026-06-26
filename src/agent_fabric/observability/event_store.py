import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event
from agent_fabric.memory.sqlite_store import get_db_conn

logger = logging.getLogger("agent_fabric.observability.event_store")


class SQLiteEventStore:
    """
    Persists all EventBus events to the SQLite database of the current workspace.
    Subscribes automatically to '*' to capture all events.
    """
    def __init__(self) -> None:
        self._ensure_table()
        # Automatically subscribe to all events on the EventBus
        event_bus.subscribe("*", self.on_event)

    def _ensure_table(self) -> None:
        """Ensure the events table exists in the database."""
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL, -- ISO datetime
                actor TEXT,
                workspace TEXT NOT NULL,
                data TEXT -- JSON string
            )
            """)
            conn.commit()

    async def on_event(self, event: Event) -> None:
        """Event handler callback that persists the published event."""
        # Avoid infinite loops: do not persist EventStore's own logging events if any are created
        if event.event_type == "EventLogged":
            return
            
        try:
            with get_db_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO events (id, event_type, timestamp, actor, workspace, data)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    event.id,
                    event.event_type,
                    event.timestamp.isoformat(),
                    event.actor,
                    event.workspace,
                    json.dumps(event.data)
                ))
        except Exception as e:
            logger.error(f"Failed to persist event {event.event_type} in EventStore: {e}")

    def query(
        self, 
        event_type: Optional[str] = None, 
        actor: Optional[str] = None, 
        limit: int = 100
    ) -> List[Event]:
        """Query stored events under the active workspace."""
        self._ensure_table()
        
        query = "SELECT * FROM events"
        where_clauses = []
        params = []
        
        if event_type:
            where_clauses.append("event_type = ?")
            params.append(event_type)
        if actor:
            where_clauses.append("actor = ?")
            params.append(actor)
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            events = []
            for row in rows:
                events.append(
                    Event(
                        id=row["id"],
                        event_type=row["event_type"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        actor=row["actor"],
                        workspace=row["workspace"],
                        data=json.loads(row["data"]) if row["data"] else {}
                    )
                )
            return events


# Global singleton instance which registers itself on import
event_store = SQLiteEventStore()
