from app.config import settings
from app.tools.types import ToolResult

def web_search(query: str) -> ToolResult:
    if settings.airgap:
        return ToolResult(ok=False, data=None, error="Web search disabled in airgap mode")
    # Placeholder: implement actual search if needed
    return ToolResult(ok=False, data=None, error="Web search not implemented")
