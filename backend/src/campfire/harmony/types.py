"""Type definitions for Harmony orchestration."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel


class HarmonyRole(str, Enum):
    """Harmony message roles."""
    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"


class ToolCall(BaseModel):
    """Represents a tool call in Harmony format."""
    recipient: str
    method: str
    args: Dict[str, Any]
    call_id: Optional[str] = None


class ToolResult(BaseModel):
    """Represents a tool result in Harmony format."""
    call_id: str
    result: Any
    error: Optional[str] = None


class HarmonyMessage(BaseModel):
    """Represents a message in Harmony conversation format."""
    role: HarmonyRole
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_results: Optional[List[ToolResult]] = None


class ToolDefinition(BaseModel):
    """Tool definition for Harmony tool registration."""
    name: str
    methods: List[Dict[str, Any]]


class ToolConfig(BaseModel):
    """Tool configuration for Harmony rendering."""
    recipient_prefix: str
    definition: ToolDefinition