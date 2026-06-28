from agent_fabric.tools.decorator import tool

__all__ = ["calendar_events", "calendar_create", "calendar_free_slots"]


@tool("Fetch calendar events for a time range")
def calendar_events(time_min: str = "today", time_max: str = "tomorrow") -> str:
    """Retrieves scheduled calendar events."""
    return f"Calendar Events: 3 events found between {time_min} and {time_max}."


@tool("Create a new Google Calendar event")
def calendar_create(summary: str, start_time: str, end_time: str) -> str:
    """Schedules a new meeting or event in Google Calendar."""
    return f"Calendar Create: Created event '{summary}' starting at {start_time}."


@tool("Find available free meeting slots")
def calendar_free_slots(date: str = "today") -> str:
    """Analyzes calendar schedule and returns open time windows."""
    return f"Calendar Free Slots: Free openings on {date}: 10:00 AM - 11:30 AM, 3:00 PM - 4:00 PM."
