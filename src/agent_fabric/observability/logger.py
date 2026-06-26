import os
import logging
from pathlib import Path
from agent_fabric.core.workspace import Workspace

logger = logging.getLogger("agent_fabric.observability.logger")


def setup_agent_logger(agent_name: str) -> logging.Logger:
    """
    Sets up and configures a file logger specifically for an agent instance.
    Logs are isolated under the active workspace logs directory (~/.agentfabric/workspaces/<ws>/logs/<agent_name>.log).
    """
    workspace = Workspace.current()
    workspace.ensure_exists()
    
    agent_logger = logging.getLogger(f"agent_fabric.agents.{agent_name}")
    agent_logger.setLevel(logging.INFO)
    
    # Prevent propagation to parent loggers to avoid duplicate CLI printing
    agent_logger.propagate = False
    
    # Remove existing handlers to prevent duplicate configurations
    agent_logger.handlers.clear()
    
    log_file_path = workspace.logs_path / f"{agent_name}.log"
    
    try:
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
        )
        file_handler.setFormatter(formatter)
        agent_logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Failed to setup file logging for agent '{agent_name}': {e}")
        
    return agent_logger
