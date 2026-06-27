import json
import sqlite3
import time
import uuid
import logging
from typing import List, Any, Optional
from pydantic import BaseModel, Field
from agent_fabric.core.workspace import Workspace

logger = logging.getLogger("agent_fabric.scheduler.history")

__all__ = ["ScheduleExecution", "ScheduleHistoryStore"]


class ScheduleExecution(BaseModel):
    """Execution state and audit tracking record for scheduled tasks."""
    execution_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    schedule_id: str
    trigger_time: float = Field(default_factory=time.time)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    status: str = "pending"  # pending, running, completed, failed
    output: Optional[Any] = None
    error: Optional[str] = None


class ScheduleHistoryStore:
    """
    Thread-safe SQLite storage manager for schedule definitions and execution histories.
    """
    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        if self._db_path:
            path = self._db_path
        else:
            workspace = Workspace.current()
            path = str(workspace.path / "scheduler.db")
        conn = sqlite3.connect(path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize tables for schedules and execution history."""
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                trigger_config TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_name TEXT NOT NULL,
                inputs TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                created_at REAL NOT NULL
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule_executions (
                execution_id TEXT PRIMARY KEY,
                schedule_id TEXT NOT NULL,
                trigger_time REAL NOT NULL,
                start_time REAL,
                end_time REAL,
                status TEXT NOT NULL,
                output TEXT,
                error TEXT,
                FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE CASCADE
            );
            """)
            conn.commit()

    def record_execution_start(self, execution: ScheduleExecution) -> None:
        self.init_db()
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO schedule_executions (execution_id, schedule_id, trigger_time, start_time, status)
            VALUES (?, ?, ?, ?, ?)
            """, (
                execution.execution_id,
                execution.schedule_id,
                execution.trigger_time,
                execution.start_time or time.time(),
                execution.status
            ))
            conn.commit()

    def record_execution_complete(self, execution_id: str, output: Any) -> None:
        with self._get_connection() as conn:
            out_str = json.dumps(output, default=str) if output is not None else None
            conn.execute("""
            UPDATE schedule_executions
            SET end_time = ?, status = 'completed', output = ?
            WHERE execution_id = ?
            """, (time.time(), out_str, execution_id))
            conn.commit()

    def record_execution_failed(self, execution_id: str, error: str) -> None:
        with self._get_connection() as conn:
            conn.execute("""
            UPDATE schedule_executions
            SET end_time = ?, status = 'failed', error = ?
            WHERE execution_id = ?
            """, (time.time(), error, execution_id))
            conn.commit()

    def get_history(self, schedule_id: str, limit: int = 20) -> List[ScheduleExecution]:
        self.init_db()
        with self._get_connection() as conn:
            cursor = conn.execute("""
            SELECT * FROM schedule_executions
            WHERE schedule_id = ?
            ORDER BY trigger_time DESC
            LIMIT ?
            """, (schedule_id, limit))
            rows = cursor.fetchall()
            
        results = []
        for row in rows:
            out = json.loads(row["output"]) if row["output"] else None
            results.append(ScheduleExecution(
                execution_id=row["execution_id"],
                schedule_id=row["schedule_id"],
                trigger_time=row["trigger_time"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                status=row["status"],
                output=out,
                error=row["error"]
            ))
        return results
