import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel, Field

from agent_fabric.core.config import settings
from agent_fabric.core.models import Event
from agent_fabric.core.events import event_bus
from agent_fabric.core.workspace import Workspace, validate_workspace_name
from agent_fabric.memory.engine import memory_engine
from agent_fabric.runtime.agent import Agent, validate_agent_name
from agent_fabric.runtime.team import Team
from agent_fabric.pipelines.dag import Pipeline
from agent_fabric.pipelines.executor import PipelineExecutor
from agent_fabric.scheduler.scheduler import Schedule, scheduler_engine

logger = logging.getLogger("agent_fabric.server.app")

__all__ = ["create_app"]


# Request/Response schemas
class AgentRunRequest(BaseModel):
    agent_name: str
    task: str
    provider: Optional[str] = None
    model: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_steps: int = 10


class TeamRunRequest(BaseModel):
    task: str
    team_name: str = "team"
    strategy: str = "sequential"
    agents: List[Dict[str, Any]] = Field(default_factory=list)
    supervisor: Optional[Dict[str, Any]] = None


class PipelineRunRequest(BaseModel):
    pipeline: Dict[str, Any]
    inputs: Dict[str, Any] = Field(default_factory=dict)


class ScheduleCreateRequest(BaseModel):
    name: str
    trigger_type: str
    trigger_config: Dict[str, Any]
    target_type: str
    target_name: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class MemoryStoreRequest(BaseModel):
    text: str
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    agent_id: Optional[str] = None
    importance_score: float = 1.0


class WorkspaceCreateRequest(BaseModel):
    name: str


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="AgentFabric Server API",
        description="REST and WebSocket control server for the AgentFabric runtime.",
        version="0.1.0"
    )

    # --- REST Routes ---

    @app.post("/agents/run")
    async def run_agent(req: AgentRunRequest):
        """Execute a task on a dynamically configured Agent instance."""
        try:
            agent_name = validate_agent_name(req.agent_name)
            max_steps = max(1, min(req.max_steps, 50))
            
            agent = Agent(
                name=agent_name,
                model=req.model,
                tools=req.tools,
                system_prompt=req.system_prompt,
                provider=req.provider,
                temperature=req.temperature
            )
            res = await agent.run(req.task, max_steps=max_steps)
            
            for handler in list(agent.logger.handlers):
                handler.close()
            agent.logger.handlers.clear()
            
            return {
                "text": res.text,
                "messages": list(res.messages)
            }
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Error running agent {req.agent_name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error executing agent run.")

    @app.post("/teams/run")
    async def run_team(req: TeamRunRequest):
        """Execute a task on a dynamically configured Team instance."""
        try:
            team = Team.from_dict({
                "name": req.team_name,
                "strategy": req.strategy,
                "agents": req.agents,
                "supervisor": req.supervisor
            })
            res = await team.run(req.task)
            return {
                "text": res.text,
                "outputs": res.outputs
            }
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Error running team {req.team_name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error executing team run.")

    @app.post("/pipelines/run")
    async def run_pipeline(req: PipelineRunRequest):
        """Execute a DAG workflow pipeline on an input context."""
        try:
            pipeline_inst = Pipeline(**req.pipeline)
            executor = PipelineExecutor(pipeline_inst)
            run_record = await executor.run(req.inputs)
            return run_record.model_dump()
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Error running pipeline: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error executing pipeline run.")

    @app.post("/schedules")
    async def create_schedule_endpoint(req: ScheduleCreateRequest):
        """Register a new job schedule."""
        try:
            schedule_inst = Schedule(**req.model_dump())
            created = scheduler_engine.create_schedule(schedule_inst)
            return created.model_dump()
        except Exception as e:
            logger.error(f"Error creating schedule: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/schedules")
    async def list_schedules_endpoint():
        """List active job schedules."""
        return [s.model_dump() for s in scheduler_engine.list_schedules()]

    @app.put("/schedules/{id}/pause")
    async def pause_schedule_endpoint(id: str):
        """Pause an active schedule."""
        scheduler_engine.pause_schedule(id)
        return {"status": "paused", "id": id}

    @app.delete("/schedules/{id}")
    async def delete_schedule_endpoint(id: str):
        """Delete a schedule."""
        scheduler_engine.delete_schedule(id)
        return {"status": "deleted", "id": id}

    @app.get("/schedules/{id}/history")
    async def get_schedule_history_endpoint(id: str):
        """Retrieve execution history for a schedule."""
        history = scheduler_engine.history_store.get_history(id)
        return [h.model_dump() for h in history]

    @app.get("/agents/{name}/logs")
    async def get_agent_logs(name: str):
        """Retrieve the isolated log execution history for a given agent."""
        try:
            clean_name = validate_agent_name(name)
            workspace = Workspace.current()
            log_file = workspace.logs_path / f"{clean_name}.log"
            if not log_file.exists():
                return []
            
            logs = []
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line.strip()))
                    except Exception:
                        pass
            return logs
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Error reading logs for agent {name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error reading logs.")

    @app.post("/memory/store")
    async def store_memory(req: MemoryStoreRequest):
        """Persist a memory string to SQLite and configured vector databases."""
        try:
            if req.agent_id:
                validate_agent_name(req.agent_id)
            record_id = await memory_engine.store(
                text=req.text,
                tags=req.tags,
                metadata=req.metadata,
                agent_id=req.agent_id,
                importance_score=req.importance_score
            )
            return {"id": record_id}
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Error storing memory: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error storing memory.")

    @app.get("/memory/search")
    async def search_memory(
        query: str = Query(..., description="Query terms to search"),
        limit: int = Query(5, description="Maximum results to return"),
        tag: Optional[str] = Query(None, description="Optional tag filter"),
        agent_id: Optional[str] = Query(None, description="Optional agent owner ID filter")
    ):
        """Search memory index using semantic vector similarity or full-text FTS5 queries."""
        filters = {}
        if tag:
            filters["tag"] = tag
        if agent_id:
            try:
                filters["agent_id"] = validate_agent_name(agent_id)
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))
            
        try:
            clamped_limit = max(1, min(limit, 100))
            results = await memory_engine.search(query, limit=clamped_limit, filters=filters)
            return [
                {
                    "id": m.id,
                    "text": m.text,
                    "tags": m.tags,
                    "metadata": m.metadata,
                    "agent_id": m.agent_id,
                    "created_at": m.created_at.isoformat(),
                    "importance_score": m.importance_score
                }
                for m in results
            ]
        except Exception as e:
            logger.error(f"Error searching memory: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error searching memory.")

    @app.get("/workspaces")
    async def list_workspaces():
        """List all isolated workspaces currently defined on disk."""
        try:
            configs = [w.get_config() for w in Workspace.list_all()]
            return [c.model_dump() for c in configs]
        except Exception as e:
            logger.error(f"Error listing workspaces: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error listing workspaces.")

    @app.post("/workspaces")
    async def create_workspace(req: WorkspaceCreateRequest):
        """Create a new isolated workspace folder and select it as current."""
        try:
            clean_name = validate_workspace_name(req.name)
            ws = Workspace.get(clean_name)
            ws.ensure_exists()
            settings.current_workspace = clean_name
            return ws.get_config().model_dump()
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Error creating workspace {req.name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error creating workspace.")

    # --- WebSocket Route ---

    @app.websocket("/events")
    async def websocket_events(websocket: WebSocket):
        """WebSocket connection streaming real-time EventBus events to subscribers."""
        await websocket.accept()
        logger.info("WebSocket client connected to event stream.")
        
        async def send_event(event: Event) -> None:
            try:
                await websocket.send_text(event.model_dump_json())
            except Exception:
                pass
                
        event_bus.subscribe("*", send_event)
        
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected from event stream.")
        except Exception as e:
            logger.warning(f"WebSocket client error on event stream: {e}")
        finally:
            event_bus.unsubscribe("*", send_event)

    return app

