import asyncio
import logging
from typing import Callable, Awaitable, Dict, Set, Any, List
from agent_fabric.core.models import Event

logger = logging.getLogger("agent_fabric.events")


class EventBus:
    """
    In-process EventBus for AgentFabric utilizing asyncio.
    Supports publish/subscribe messaging and request/response RPC patterns.
    """
    def __init__(self):
        self._subscribers: Dict[str, Set[Callable[[Event], Awaitable[None]]]] = {}
        self._request_handlers: Dict[str, Callable[[Event], Awaitable[Any]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        """Subscribe a handler to a specific event type, or '*' for all events."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        self._subscribers[event_type].add(handler)
        logger.debug(f"Subscribed handler to event type: {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(handler)
            logger.debug(f"Unsubscribed handler from event type: {event_type}")

    async def publish(self, event: Event) -> None:
        """Publish an event to all registered subscribers concurrently."""
        handlers = list(self._subscribers.get(event.event_type, []))
        # Support wildcard subscribers
        handlers.extend(list(self._subscribers.get("*", [])))

        if not handlers:
            return

        # Fire all handlers concurrently
        tasks = []
        for handler in handlers:
            tasks.append(self._safe_execute(handler, event))
        
        await asyncio.gather(*tasks)

    async def _safe_execute(self, handler: Callable[[Event], Awaitable[None]], event: Event) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Error in event handler for {event.event_type}: {e}", exc_info=True)

    def register_request_handler(self, request_type: str, handler: Callable[[Event], Awaitable[Any]]) -> None:
        """Register a single handler to respond to request-response RPC calls."""
        if request_type in self._request_handlers:
            logger.warning(f"Overwriting request handler for: {request_type}")
        self._request_handlers[request_type] = handler
        logger.debug(f"Registered request handler for: {request_type}")

    def unregister_request_handler(self, request_type: str) -> None:
        """Unregister the handler for a request type."""
        self._request_handlers.pop(request_type, None)

    async def request(self, event: Event) -> Any:
        """Send a request event and wait for the handler to return a result."""
        handler = self._request_handlers.get(event.event_type)
        if not handler:
            raise ValueError(f"No request handler registered for event type: {event.event_type}")
        return await handler(event)


# Global EventBus instance
event_bus = EventBus()
