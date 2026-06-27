import json
import logging
from agent_fabric.core.workspace import Workspace

logger = logging.getLogger("agent_fabric.observability.logger")

__all__ = ["setup_agent_logger", "JsonFormatter"]


class JsonFormatter(logging.Formatter):
    """Formats log records as strict valid single-line JSON objects."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_agent_logger(agent_name: str) -> logging.Logger:
    """
    Sets up and configures a file logger specifically for an agent instance.
    Logs are isolated under the active workspace logs directory (~/.agentfabric/workspaces/<ws>/logs/<agent_name>.log).
    """
    workspace = Workspace.current()
    workspace.ensure_exists()
    
    agent_logger = logging.getLogger(f"agent_fabric.agents.{agent_name}")
    agent_logger.setLevel(logging.INFO)
    agent_logger.propagate = False
    agent_logger.handlers.clear()
    
    log_file_path = workspace.logs_path / f"{agent_name}.log"
    
    try:
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        agent_logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Failed to setup file logging for agent '{agent_name}': {e}")
        
    return agent_logger

