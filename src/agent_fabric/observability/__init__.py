"""
AgentFabric Observability and Execution Tracking.
Implements structured logging, execution metrics, and event log persistence.
"""
from agent_fabric.observability.event_store import event_store
from agent_fabric.observability.logger import setup_agent_logger
