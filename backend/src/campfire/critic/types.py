"""Type definitions for the Safety Critic system."""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


class CriticStatus(Enum):
    """Status of Safety Critic decision."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass
class CriticDecision:
    """Decision made by the Safety Critic."""
    status: CriticStatus
    reasons: List[str]
    fixes: Optional[List[str]] = None
    emergency_detected: bool = False
    requires_emergency_banner: bool = False


@dataclass
class ChecklistStep:
    """Individual step in a checklist response."""
    title: str
    action: str
    source: Optional[Dict[str, Any]] = None
    caution: Optional[str] = None


@dataclass
class ChecklistResponse:
    """Complete checklist response structure."""
    checklist: List[ChecklistStep]
    meta: Dict[str, Any]