import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel, Field

from agent_fabric.core.config import settings
from agent_fabric.core.models import Event, MemoryRecord, WorkspaceConfig
from agent_fabric.core.events import event_bus
from agent_fabric.core.workspace import Workspace
from agent_fabric.memory.engine import memory_engine
from agent_fabric.runtime.agent import Agent

logger = logging.getLogger("agent_fabric.server.app")


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
            # Instantiate agent
            agent = Agent(
                name=req.agent_name,
                model=req.model,
                tools=req.tools,
                system_prompt=req.system_prompt,
                provider=req.provider,
                temperature=req.temperature
            )
            # Run task
            res = await agent.run(req.task, max_steps=req.max_steps)
            
            # Close handlers on Windows to release logs lock immediately
            for handler in agent.logger.handlers:
                handler.close()
            agent.logger.handlers.clear()
            
            return {
                "text": res.text,
                "messages": [m for m in res.messages]
            }
        except Exception as e:
            logger.error(f"Error running agent {req.agent_name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agents/{name}/logs")
    async def get_agent_logs(name: str):
        """Retrieve the isolated log execution history for a given agent."""
        try:
            workspace = Workspace.current()
            log_file = workspace.logs_path / f"{name}.log"
            if not log_file.exists():
                return []
            
            logs = []
            import json
            # Open and read without locking
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line.strip()))
                    except Exception:
                        pass
            return logs
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/memory/store")
    async def store_memory(req: MemoryStoreRequest):
        """Persist a memory string to SQLite and configured vector databases."""
        try:
            record_id = await memory_engine.store(
                text=req.text,
                tags=req.tags,
                metadata=req.metadata,
                agent_id=req.agent_id,
                importance_score=req.importance_score
            )
            return {"id": record_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

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
            filters["agent_id"] = agent_id
            
        try:
            results = await memory_engine.search(query, limit=limit, filters=filters)
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
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/workspaces")
    async def list_workspaces():
        """List all isolated workspaces currently defined on disk."""
        try:
            configs = [w.get_config() for w in Workspace.list_all()]
            return [c.model_dump() for c in configs]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/workspaces")
    async def create_workspace(req: WorkspaceCreateRequest):
        """Create a new isolated workspace folder and select it as current."""
        try:
            ws = Workspace.get(req.name)
            ws.ensure_exists()
            settings.current_workspace = req.name
            return ws.get_config().model_dump()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # --- WebSocket Route ---

    @app.websocket("/events")
    async def websocket_events(websocket: WebSocket):
        """WebSocket connection streaming real-time EventBus events to subscribers."""
        await websocket.accept()
        logger.info("WebSocket client connected to event stream.")
        
        # Define callback handler
        async def send_event(event: Event) -> None:
            try:
                # model_dump contains datetime which needs serialization handling.
                # model_dump_json() is built-in to Pydantic and returns a perfect JSON string!
                await websocket.send_text(event.model_dump_json())
            except Exception:
                # Fails silently if socket is already closed
                pass
                
        # Register wildcard subscription to intercept every published event
        event_bus.subscribe("*", send_event)
        
        try:
            while True:
                # Keep socket alive by receiving frames (acting as client ping responder)
                await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected from event stream.")
        finally:
            event_bus.unsubscribe("*", send_event)

    return app
