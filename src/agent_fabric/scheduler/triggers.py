from typing import Dict, Any
from pydantic import BaseModel, Field

__all__ = [
    "CronTriggerConfig",
    "IntervalTriggerConfig",
    "DateTriggerConfig",
    "EventTriggerConfig",
]


class CronTriggerConfig(BaseModel):
    """Configuration for cron-expression recurring schedule triggers."""
    cron_expression: str = "0 8 * * *"


class IntervalTriggerConfig(BaseModel):
    """Configuration for fixed interval recurring schedule triggers."""
    seconds: float = 60.0


class DateTriggerConfig(BaseModel):
    """Configuration for one-shot specific timestamp schedule triggers."""
    run_at: str  # ISO-8601 string or format


class EventTriggerConfig(BaseModel):
    """Configuration for reactive EventBus event triggers."""
    event_type: str
    event_filter: Dict[str, Any] = Field(default_factory=dict)
