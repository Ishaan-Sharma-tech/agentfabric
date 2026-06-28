from agent_fabric.tools.decorator import tool

__all__ = ["slack_send", "slack_read", "slack_search"]


@tool("Send message to a Slack channel")
def slack_send(channel: str, text: str) -> str:
    """Posts a message to a designated Slack channel."""
    return f"Slack Send: Posted message to #{channel}."


@tool("Read recent Slack channel messages")
def slack_read(channel: str, limit: int = 10) -> str:
    """Fetches the latest messages from a Slack channel."""
    return f"Slack Read: Retrived last {limit} messages from #{channel}."


@tool("Search Slack channel archives")
def slack_search(query: str) -> str:
    """Searches across all Slack channels for matching query text."""
    return f"Slack Search: Found 4 occurrences matching '{query}'."
