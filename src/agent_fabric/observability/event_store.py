import json
import asyncio
import logging
from typing import List, Optional, Any
from datetime import datetime
from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event
from agent_fabric.core.workspace import Workspace
from agent_fabric.memory.sqlite_store import get_db_conn

logger = logging.getLogger("agent_fabric.observability.event_store")

__all__ = ["SQLiteEventStore", "event_store"]


class SQLiteEventStore:
    """
    Persists all EventBus events to the SQLite database of the current workspace.
    Subscribes automatically to '*' to capture all events.
    """
    def __init__(self, auto_subscribe: bool = True) -> None:
        self._ensure_table()
        if auto_subscribe:
            event_bus.subscribe("*", self.on_event)

    def _ensure_table(self) -> None:
        """Ensure the events table exists in the database."""
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT,
                workspace TEXT NOT NULL,
                data TEXT
            )
            """)

    def _sync_persist(self, event: Event) -> None:
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR IGNORE INTO events (id, event_type, timestamp, actor, workspace, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                event.id,
                event.event_type,
                event.timestamp.isoformat(),
                event.actor,
                event.workspace,
                json.dumps(event.data)
            ))

    async def on_event(self, event: Event) -> None:
        """Event handler callback that persists the published event asynchronously."""
        if event.event_type == "EventLogged":
            return
            
        try:
            await asyncio.to_thread(self._sync_persist, event)
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
        ws = Workspace.current()
        
        query = "SELECT * FROM events WHERE workspace = ?"
        params: List[Any] = [ws.name]
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if actor:
            query += " AND actor = ?"
            params.append(actor)
            
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


# Global singleton instance
event_store = SQLiteEventStore()

