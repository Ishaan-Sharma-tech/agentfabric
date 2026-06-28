"""
AgentFabric official community plugins package.
"""
from agent_fabric.plugins.official.gmail import (
    gmail_read as gmail_read, 
    gmail_send as gmail_send, 
    gmail_search as gmail_search, 
    gmail_label as gmail_label
)
from agent_fabric.plugins.official.github_enhanced import (
    github_pr_review as github_pr_review, 
    github_actions_status as github_actions_status, 
    github_release as github_release
)
from agent_fabric.plugins.official.slack import (
    slack_send as slack_send, 
    slack_read as slack_read, 
    slack_search as slack_search
)
from agent_fabric.plugins.official.notion import (
    notion_read_page as notion_read_page, 
    notion_create_page as notion_create_page, 
    notion_search as notion_search
)
from agent_fabric.plugins.official.calendar import (
    calendar_events as calendar_events, 
    calendar_create as calendar_create, 
    calendar_free_slots as calendar_free_slots
)

__all__ = [
    "gmail_read", "gmail_send", "gmail_search", "gmail_label",
    "github_pr_review", "github_actions_status", "github_release",
    "slack_send", "slack_read", "slack_search",
    "notion_read_page", "notion_create_page", "notion_search",
    "calendar_events", "calendar_create", "calendar_free_slots"
]
