"""
Pydantic models for FastAPI request/response schemas.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    query: str = Field(..., description="User's emergency query", min_length=1, max_length=1000)
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for context")


class ChecklistStepResponse(BaseModel):
    """Individual step in a checklist response."""
    title: str
    action: str
    source: Optional[Dict[str, Any]] = None
    caution: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    conversation_id: str
    checklist: List[ChecklistStepResponse]
    meta: Dict[str, Any]
    emergency_banner: Optional[str] = None
    blocked: bool = False
    block_reason: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str
    timestamp: datetime
    version: str
    components: Dict[str, str]
    offline_mode: bool = True


class DocumentViewRequest(BaseModel):
    """Request model for document viewer endpoint."""
    doc_id: str = Field(..., description="Document identifier")
    start_offset: int = Field(..., description="Start position in document", ge=0)
    end_offset: int = Field(..., description="End position in document", ge=0)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "doc_id": "ifrc-2020",
                "start_offset": 1500,
                "end_offset": 2000
            }
        }
    }


class DocumentViewResponse(BaseModel):
    """Response model for document viewer endpoint."""
    doc_id: str
    doc_title: str
    text: str
    location: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None


class AdminLoginRequest(BaseModel):
    """Request model for admin authentication."""
    password: str = Field(..., description="Admin password", min_length=1)


class AdminLoginResponse(BaseModel):
    """Response model for admin authentication."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuditLogEntry(BaseModel):
    """Individual audit log entry."""
    timestamp: datetime
    query: str
    query_hash: Optional[str] = None
    response_blocked: bool
    critic_decision: Dict[str, Any]
    emergency_detected: bool
    conversation_id: Optional[str] = None
    response_time_ms: Optional[int] = None
    llm_provider: Optional[str] = None
    harmony_tokens_used: Optional[int] = None
    system_metrics: Optional[Dict[str, Any]] = None


class AuditLogResponse(BaseModel):
    """Response model for audit log endpoint."""
    logs: List[AuditLogEntry]
    total_count: int
    page: int
    page_size: int


class SystemHealthEntry(BaseModel):
    """System health monitoring entry."""
    timestamp: datetime
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_used_mb: Optional[float] = None
    disk_usage_percent: Optional[float] = None
    llm_provider_status: str
    corpus_db_status: str


class PerformanceMetric(BaseModel):
    """Performance metric entry."""
    timestamp: datetime
    endpoint: str
    response_time_ms: int
    status_code: int
    error_message: Optional[str] = None


class HarmonyDebugEntry(BaseModel):
    """Harmony debug data entry."""
    timestamp: datetime
    query: str
    harmony_debug_data: Dict[str, Any]
    harmony_tokens_used: Optional[int] = None


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime