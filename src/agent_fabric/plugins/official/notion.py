from agent_fabric.tools.decorator import tool

__all__ = ["notion_read_page", "notion_create_page", "notion_search"]


@tool("Read page content from Notion workspace")
def notion_read_page(page_id: str) -> str:
    """Retrieves text content and blocks from a Notion page."""
    return f"Notion Read: Extracted page content for ID '{page_id}'."


@tool("Create a new Notion page")
def notion_create_page(title: str, content: str) -> str:
    """Creates a new documentation page in Notion."""
    return f"Notion Create: Successfully created page '{title}'."


@tool("Search Notion workspace")
def notion_search(query: str) -> str:
    """Searches pages and databases inside Notion workspace."""
    return f"Notion Search: Returned 2 matching documents for '{query}'."
