"""Orchestrator policies — tool allow-lists, destructive-tool gates, rate limits."""

from enum import Enum
from app.config import settings

# ── Autonomy Levels ──────────────────────────────────────────────────────
class AutonomyLevel(str, Enum):
    LOW = "low"        # Reactive only — Joi responds, never initiates
    MEDIUM = "medium"  # Proactive suggestions, but always asks first
    HIGH = "high"      # Proactive actions with post-hoc notifications

def get_autonomy_level() -> AutonomyLevel:
    """Get current autonomy level from config."""
    try:
        return AutonomyLevel(settings.autonomy_level.lower())
    except ValueError:
        return AutonomyLevel.MEDIUM

def allow_proactive_suggestions() -> bool:
    """Return True if autonomy level permits proactive suggestions."""
    return get_autonomy_level() in (AutonomyLevel.MEDIUM, AutonomyLevel.HIGH)

def allow_proactive_actions() -> bool:
    """Return True if autonomy level permits proactive actions without pre-approval."""
    return get_autonomy_level() == AutonomyLevel.HIGH

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
    # In HIGH autonomy, still require approval for destructive tools
    # (safety net — only proactive *suggestions* bypass the ask)
    return tool_name in DESTRUCTIVE_TOOLS


def is_allowed_tool(tool_name: str) -> bool:
    """Return True if *tool_name* is in the read-only allow-list."""
    return tool_name in ALLOWED_READ_TOOLS
