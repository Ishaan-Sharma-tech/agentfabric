import pytest
from agent_fabric.providers.openrouter import OpenRouterProvider
from agent_fabric.plugins.official import (
    gmail_read, gmail_send, gmail_search, gmail_label,
    github_pr_review, github_actions_status, github_release,
    slack_send, slack_read, slack_search,
    notion_read_page, notion_create_page, notion_search,
    calendar_events, calendar_create, calendar_free_slots
)


@pytest.mark.asyncio
async def test_openrouter_provider():
    """Verify OpenRouter provider chat completions."""
    provider = OpenRouterProvider()
    res = await provider.chat([{"role": "user", "content": "Hello OpenRouter"}])
    assert "OpenRouter" in res["content"]


def test_official_community_plugins():
    """Verify execution of all official community plugin tools."""
    # Gmail
    assert "Fetched" in gmail_read()
    assert "sent email" in gmail_send(to="test@example.com", subject="Test", body="Hello")
    assert "Found" in gmail_search(query="test")
    assert "Applied label" in gmail_label(msg_id="123", label="important")
    
    # GitHub Enhanced
    assert "Evaluated PR" in github_pr_review(repo="org/repo", pr_id=10)
    assert "passing" in github_actions_status(repo="org/repo")
    assert "Created release" in github_release(repo="org/repo", tag="v1.0.0")
    
    # Slack
    assert "Posted message" in slack_send(channel="general", text="Hello team")
    assert "Retrived" in slack_read(channel="general")
    assert "occurrences" in slack_search(query="standup")
    
    # Notion
    assert "Extracted" in notion_read_page(page_id="page_123")
    assert "created page" in notion_create_page(title="Specs", content="Doc text")
    assert "Returned" in notion_search(query="specs")
    
    # Calendar
    assert "events found" in calendar_events()
    assert "Created event" in calendar_create(summary="Sync", start_time="10:00", end_time="11:00")
    assert "Free openings" in calendar_free_slots()
