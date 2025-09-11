"""
FastAPI backend server for Campfire emergency helper.

This module provides the REST API endpoints for the offline emergency
guidance system, orchestrating LLM inference, document search, and
safety validation.
"""

from .main import create_app
from .models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    DocumentViewRequest,
    DocumentViewResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AuditLogResponse,
)

__all__ = [
    "create_app",
    "ChatRequest",
    "ChatResponse", 
    "HealthResponse",
    "DocumentViewRequest",
    "DocumentViewResponse",
    "AdminLoginRequest",
    "AdminLoginResponse",
    "AuditLogResponse",
]