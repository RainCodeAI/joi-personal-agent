from typing import Dict, Any
from pydantic import BaseModel

class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]

class ToolResult(BaseModel):
    ok: bool
    data: Any
    error: str = ""
