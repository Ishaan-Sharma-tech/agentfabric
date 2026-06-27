import json
import time
import uuid
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event
from agent_fabric.scheduler.history import ScheduleExecution, ScheduleHistoryStore
from agent_fabric.runtime.agent import Agent
from agent_fabric.runtime.team import Team
from agent_fabric.tools.registry import tool_registry

logger = logging.getLogger("agent_fabric.scheduler.scheduler")

__all__ = ["Schedule", "SchedulerEngine", "scheduler_engine"]


class Schedule(BaseModel):
    """Declarative job schedule configuration model."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    trigger_type: str  # cron, interval, date, event
    trigger_config: Dict[str, Any]
    target_type: str  # agent, team, pipeline, tool
    target_name: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: float = Field(default_factory=time.time)


class SchedulerEngine:
    """
    Autonomous scheduler engine managing background timers, cron loops,
    EventBus event triggers, and persistent execution state.
    """
    def __init__(self, history_store: Optional[ScheduleHistoryStore] = None) -> None:
        self.history_store = history_store or ScheduleHistoryStore()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._event_unsubscribers: Dict[str, Any] = {}

    def _save_schedule(self, schedule: Schedule) -> None:
        self.history_store.init_db()
        with self.history_store._get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO schedules (id, name, trigger_type, trigger_config, target_type, target_name, inputs, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                schedule.id,
                schedule.name,
                schedule.trigger_type,
                json.dumps(schedule.trigger_config),
                schedule.target_type,
                schedule.target_name,
                json.dumps(schedule.inputs),
                1 if schedule.enabled else 0,
                schedule.created_at
            ))
            conn.commit()

    def create_schedule(self, schedule: Schedule) -> Schedule:
        """Create and register a new schedule."""
        self._save_schedule(schedule)
        if schedule.enabled:
            self._start_schedule_job(schedule)
        return schedule

    def list_schedules(self) -> List[Schedule]:
        self.history_store.init_db()
        with self.history_store._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM schedules ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
        results = []
        for row in rows:
            results.append(Schedule(
                id=row["id"],
                name=row["name"],
                trigger_type=row["trigger_type"],
                trigger_config=json.loads(row["trigger_config"]),
                target_type=row["target_type"],
                target_name=row["target_name"],
                inputs=json.loads(row["inputs"]),
                enabled=bool(row["enabled"]),
                created_at=row["created_at"]
            ))
        return results

    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        for s in self.list_schedules():
            if s.id == schedule_id or s.name == schedule_id:
                return s
        return None

    def pause_schedule(self, schedule_id: str) -> None:
        schedule = self.get_schedule(schedule_id)
        if schedule:
            schedule.enabled = False
            self._save_schedule(schedule)
            self._stop_schedule_job(schedule.id)

    def resume_schedule(self, schedule_id: str) -> None:
        schedule = self.get_schedule(schedule_id)
        if schedule:
            schedule.enabled = True
            self._save_schedule(schedule)
            self._start_schedule_job(schedule)

    def delete_schedule(self, schedule_id: str) -> None:
        schedule = self.get_schedule(schedule_id)
        if schedule:
            self._stop_schedule_job(schedule.id)
            with self.history_store._get_connection() as conn:
                conn.execute("DELETE FROM schedules WHERE id = ?", (schedule.id,))
                conn.commit()

    def _stop_schedule_job(self, schedule_id: str) -> None:
        if schedule_id in self._active_tasks:
            self._active_tasks[schedule_id].cancel()
            del self._active_tasks[schedule_id]
        if schedule_id in self._event_unsubscribers:
            unsub = self._event_unsubscribers.pop(schedule_id)
            if callable(unsub):
                unsub()

    def _start_schedule_job(self, schedule: Schedule) -> None:
        self._stop_schedule_job(schedule.id)
        
        ttype = schedule.trigger_type.lower()
        if ttype == "interval":
            sec = float(schedule.trigger_config.get("seconds", 60.0))
            
            async def _interval_loop():
                while True:
                    await asyncio.sleep(sec)
                    await self.execute_target(schedule)
                    
            task = asyncio.create_task(_interval_loop())
            self._active_tasks[schedule.id] = task

        elif ttype == "event":
            target_event_type = schedule.trigger_config.get("event_type")
            
            async def _on_event_triggered(event: Event):
                if target_event_type == "*" or event.event_type == target_event_type:
                    await self.execute_target(schedule)
                    
            unsub = event_bus.subscribe(target_event_type or "*", _on_event_triggered)
            self._event_unsubscribers[schedule.id] = unsub

    async def execute_target(self, schedule: Schedule) -> Any:
        """Executes the target workload (agent, team, pipeline, tool) for a schedule."""
        execution = ScheduleExecution(schedule_id=schedule.id, start_time=time.time(), status="running")
        self.history_store.record_execution_start(execution)
        
        try:
            target_type = schedule.target_type.lower()
            inputs = dict(schedule.inputs)
            
            if target_type == "agent":
                agent = Agent(name=schedule.target_name)
                task = inputs.get("task") or inputs.get("prompt") or "Scheduled task"
                res = await agent.run(task)
                out = res.text
            elif target_type == "team":
                team = Team(agents=[Agent(name="worker1")], name=schedule.target_name)
                task = inputs.get("task") or "Scheduled team task"
                res = await team.run(task)
                out = res.text
            elif target_type == "pipeline":
                from agent_fabric.pipelines.dag import Pipeline
                from agent_fabric.pipelines.executor import PipelineExecutor
                pipeline = Pipeline(name=schedule.target_name)
                executor = PipelineExecutor(pipeline)
                res = await executor.run(inputs)
                out = res.outputs
            elif target_type == "tool":
                tool_inst = tool_registry.get(schedule.target_name)
                if not tool_inst:
                    raise ValueError(f"Tool '{schedule.target_name}' not found.")
                out = await tool_inst.execute(**inputs)
            else:
                raise ValueError(f"Unsupported target type '{schedule.target_type}'.")
                
            self.history_store.record_execution_complete(execution.execution_id, out)
            return out
        except Exception as e:
            logger.error(f"Execution of schedule '{schedule.id}' failed: {e}", exc_info=True)
            self.history_store.record_execution_failed(execution.execution_id, str(e))
            raise e

    def start_all(self) -> None:
        """Bootstraps all enabled persistent schedules on startup."""
        for schedule in self.list_schedules():
            if schedule.enabled:
                self._start_schedule_job(schedule)


# Global singleton instance
scheduler_engine = SchedulerEngine()
