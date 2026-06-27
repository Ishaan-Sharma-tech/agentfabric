import time
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List
from agent_fabric.core.events import event_bus
from agent_fabric.core.models import Event, ToolCall
from agent_fabric.core.permissions import Capability, check_permission, AgentFabricPermissionError
from agent_fabric.core.workspace import Workspace
from agent_fabric.tools.registry import tool_registry

logger = logging.getLogger("agent_fabric.tools.runtime")

__all__ = ["ToolExecutor"]


class ToolExecutor:
    """
    Executes registered tools within capability-based security boundaries.
    Emits observability events and handles execution life cycles.
    """
    def __init__(self, agent_name: str, capabilities: List[Capability]):
        self.agent_name = agent_name
        self.capabilities = capabilities

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Executes a tool by name with arguments.
        Enforces permissions and logs invocation metrics.
        """
        tool = tool_registry.get(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' is not registered in the system.")

        # 1. Permission Check
        required_cap = getattr(
            tool, 
            "required_capability", 
            Capability(resource="tool", action="execute", scope=tool_name)
        )
        
        if not check_permission(self.capabilities, required_cap):
            raise AgentFabricPermissionError(required_cap, self.agent_name)

        # 2. ToolCall Lifecycle Init
        tool_call = ToolCall(name=tool_name, arguments=arguments)
        
        invoked_event = Event(
            event_type="ToolInvoked",
            actor=f"agent:{self.agent_name}",
            workspace=Workspace.current().name,
            data={
                "tool_call_id": tool_call.id,
                "tool_name": tool_name,
                "arguments": arguments,
                "started_at": tool_call.started_at.isoformat()
            }
        )
        await event_bus.publish(invoked_event)

        # 3. Execution Block
        start_time = time.perf_counter()
        result = None
        error_msg = None
        
        try:
            arg_keys = list(arguments.keys()) if isinstance(arguments, dict) else []
            logger.info(f"Agent '{self.agent_name}' invoking tool '{tool_name}' with parameters {arg_keys}")
            result = await tool.execute(**arguments)
            
            if not isinstance(result, str):
                result = str(result)
                
            tool_call.result = result
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            tool_call.error = error_msg
            logger.error(f"Error executing tool '{tool_name}': {error_msg}")
        finally:
            tool_call.finished_at = datetime.now(timezone.utc)
            duration = time.perf_counter() - start_time
            
            result_event = Event(
                event_type="ToolResult",
                actor=f"agent:{self.agent_name}",
                workspace=Workspace.current().name,
                data={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_name,
                    "result": tool_call.result,
                    "error": tool_call.error,
                    "duration_seconds": duration,
                    "finished_at": tool_call.finished_at.isoformat()
                }
            )
            await event_bus.publish(result_event)

        if tool_call.error:
            raise RuntimeError(f"Tool execution failed: {tool_call.error}")
            
        return tool_call.result

