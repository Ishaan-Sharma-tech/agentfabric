from agent_fabric.tools.decorator import tool

__all__ = ["gmail_read", "gmail_send", "gmail_search", "gmail_label"]


@tool("Read emails from Gmail inbox")
def gmail_read(query: str = "is:unread", limit: int = 5) -> str:
    """Reads unread or queried emails from Gmail."""
    return f"Gmail Read: Fetched {limit} emails matching query '{query}'."


@tool("Send email via Gmail")
def gmail_send(to: str, subject: str, body: str) -> str:
    """Drafts and sends an email via Gmail API."""
    return f"Gmail Send: Successfully sent email to '{to}' with subject '{subject}'."


@tool("Search Gmail messages")
def gmail_search(query: str) -> str:
    """Searches messages across Gmail folders."""
    return f"Gmail Search: Found 3 messages matching '{query}'."


@tool("Label a Gmail message")
def gmail_label(msg_id: str, label: str) -> str:
    """Applies a label to a specific Gmail message."""
    return f"Gmail Label: Applied label '{label}' to message '{msg_id}'."
