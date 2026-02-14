"""Orchestrator policies — tool allow-lists, destructive-tool gates, rate limits."""

from app.config import settings

# Tools that require explicit user confirmation before execution.
DESTRUCTIVE_TOOLS = [
    "send_email",
    "create_event",
    "file_write",
    "file_delete",
    "delete_event",
]

# Tools the agent may invoke without approval.
ALLOWED_READ_TOOLS = [
    "list_threads",
    "summarize_threads",
    "upcoming_events",
    "ingest_files",
    "search_files",
    "web_search",
]

# Maximum characters accepted from user input (enforced by PromptGuard).
MAX_INPUT_LENGTH = 4_000

# Per-tool rate limits: tool_name → max calls per session per minute.
RATE_LIMITS = {
    "send_email": 3,
    "create_event": 5,
    "file_write": 10,
    "web_search": 10,
}


def require_user_approval(tool_name: str) -> bool:
    """Return True if *tool_name* requires explicit user confirmation."""
    return tool_name in DESTRUCTIVE_TOOLS


def is_allowed_tool(tool_name: str) -> bool:
    """Return True if *tool_name* is in the read-only allow-list."""
    return tool_name in ALLOWED_READ_TOOLS
