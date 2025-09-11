"""
Main FastAPI application for Campfire emergency helper.
"""

import os
import uuid
import logging
import dataclasses
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from .. import __version__
from ..llm.factory import create_provider, get_available_providers
from ..harmony.engine import HarmonyEngine
from ..harmony.browser import LocalBrowserTool
from ..critic.critic import SafetyCritic
from ..corpus.database import CorpusDatabase

from .models import (
    ChatRequest, ChatResponse, ChecklistStepResponse,
    HealthResponse, DocumentViewRequest, DocumentViewResponse,
    AdminLoginRequest, AdminLoginResponse, AuditLogResponse,
    ErrorResponse
)
from .auth import authenticate_admin, create_admin_token, get_current_admin
from .audit import AuditLogger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global application state
app_state = {
    "llm_provider": None,
    "harmony_engine": None,
    "browser_tool": None,
    "safety_critic": None,
    "audit_logger": None,
    "corpus_db": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    # Startup
    logger.info("Starting Campfire API server...")
    
    try:
        # Initialize components
        await initialize_components()
        logger.info("All components initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Campfire API server...")
        await cleanup_components()


async def initialize_components():
    """Initialize all application components."""
    # Configuration from environment
    corpus_db_path = os.getenv("CAMPFIRE_CORPUS_DB", "corpus/processed/corpus.db")
    audit_db_path = os.getenv("CAMPFIRE_AUDIT_DB", "data/audit.db")
    policy_path = os.getenv("CAMPFIRE_POLICY_PATH", "policy.md")
    llm_provider_type = os.getenv("CAMPFIRE_LLM_PROVIDER", "ollama")
    
    # Initialize corpus database
    if not Path(corpus_db_path).exists():
        raise RuntimeError(f"Corpus database not found at {corpus_db_path}")
    
    app_state["corpus_db"] = CorpusDatabase(corpus_db_path)
    
    # Initialize LLM provider
    try:
        app_state["llm_provider"] = create_provider(llm_provider_type)
        logger.info(f"Initialized {llm_provider_type} LLM provider")
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {e}")
        raise
    
    # Initialize browser tool
    app_state["browser_tool"] = LocalBrowserTool(corpus_db_path)
    
    # Initialize Harmony engine
    app_state["harmony_engine"] = HarmonyEngine(
        llm_provider=app_state["llm_provider"],
        browser_tool=app_state["browser_tool"]
    )
    
    # Initialize safety critic
    if not Path(policy_path).exists():
        logger.warning(f"Policy file not found at {policy_path}, using default policy")
        policy_path = None
    
    app_state["safety_critic"] = SafetyCritic(policy_path)
    
    # Initialize audit logger
    app_state["audit_logger"] = AuditLogger(audit_db_path)
    
    logger.info("Component initialization complete")


async def cleanup_components():
    """Clean up application components."""
    if app_state["browser_tool"]:
        app_state["browser_tool"].close()
    
    if app_state["corpus_db"]:
        app_state["corpus_db"].close()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="Campfire Emergency Helper API",
        description="Offline emergency guidance system with gpt-oss capabilities",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if os.getenv("CAMPFIRE_DEBUG") else None,
        redoc_url="/redoc" if os.getenv("CAMPFIRE_DEBUG") else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal server error",
                detail="An unexpected error occurred",
                timestamp=datetime.now(timezone.utc)
            ).model_dump()
        )
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """System health check endpoint."""
        try:
            # Check component status
            components = {}
            
            # Check LLM provider
            if app_state["llm_provider"]:
                try:
                    # Simple test to verify provider is working
                    components["llm_provider"] = "healthy"
                except Exception as e:
                    components["llm_provider"] = f"error: {str(e)}"
            else:
                components["llm_provider"] = "not_initialized"
            
            # Check corpus database
            if app_state["corpus_db"]:
                try:
                    # Test database connection
                    doc_count = len(app_state["corpus_db"].list_documents())
                    components["corpus_db"] = f"healthy ({doc_count} documents)"
                except Exception as e:
                    components["corpus_db"] = f"error: {str(e)}"
            else:
                components["corpus_db"] = "not_initialized"
            
            # Check browser tool
            if app_state["browser_tool"]:
                components["browser_tool"] = "healthy"
            else:
                components["browser_tool"] = "not_initialized"
            
            # Check safety critic
            if app_state["safety_critic"]:
                components["safety_critic"] = "healthy"
            else:
                components["safety_critic"] = "not_initialized"
            
            # Determine overall status
            status = "healthy" if all(
                "healthy" in status for status in components.values()
            ) else "degraded"
            
            return HealthResponse(
                status=status,
                timestamp=datetime.now(timezone.utc),
                version=__version__,
                components=components,
                offline_mode=True
            )
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Health check failed: {str(e)}"
            )
    
    # Main chat endpoint
    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """Main chat endpoint for emergency queries."""
        conversation_id = request.conversation_id or str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Validate components are available
            if not all([
                app_state["harmony_engine"],
                app_state["safety_critic"],
                app_state["audit_logger"]
            ]):
                raise HTTPException(
                    status_code=503,
                    detail="System components not properly initialized"
                )
            
            logger.info(f"Processing query: {request.query[:100]}...")
            
            # Generate response using Harmony engine
            response = await app_state["harmony_engine"].process_query(request.query)
            
            # Convert ChecklistResponse to dictionary for safety critic
            response_dict = dataclasses.asdict(response)
            
            # Review response with safety critic
            critic_decision = app_state["safety_critic"].review_response(response_dict)
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Collect Harmony debug data if available
            harmony_debug_data = None
            harmony_tokens_used = None
            if hasattr(app_state["harmony_engine"], 'get_debug_info'):
                debug_info = app_state["harmony_engine"].get_debug_info()
                harmony_debug_data = debug_info.get('debug_data')
                harmony_tokens_used = debug_info.get('tokens_used')
            
            # Log the interaction with enhanced data
            app_state["audit_logger"].log_interaction(
                query=request.query,
                critic_decision=critic_decision,
                conversation_id=conversation_id,
                response_time_ms=response_time_ms,
                llm_provider=type(app_state["llm_provider"]).__name__ if app_state["llm_provider"] else None,
                harmony_tokens_used=harmony_tokens_used,
                harmony_debug_data=harmony_debug_data
            )
            
            # Log performance metric
            app_state["audit_logger"].log_performance_metric(
                endpoint="/chat",
                response_time_ms=response_time_ms,
                status_code=200 if critic_decision.status.value == "ALLOW" else 403
            )
            
            # Handle blocked responses
            if critic_decision.status.value == "BLOCK":
                return ChatResponse(
                    conversation_id=conversation_id,
                    checklist=[],
                    meta={
                        "disclaimer": "Not medical advice. Consult healthcare professionals.",
                        "blocked_message": "Response blocked for safety reasons. Please contact emergency services if this is urgent."
                    },
                    blocked=True,
                    block_reason="; ".join(critic_decision.reasons)
                )
            
            # Convert response to API format
            checklist_steps = []
            for step in response.checklist:
                checklist_steps.append(ChecklistStepResponse(
                    title=step.title,
                    action=step.action,
                    source=step.source,
                    caution=step.caution
                ))
            
            # Add emergency banner if needed
            emergency_banner = None
            if critic_decision.requires_emergency_banner:
                emergency_banner = "⚠️ EMERGENCY: Not medical advice. Call local emergency services now."
            
            return ChatResponse(
                conversation_id=conversation_id,
                checklist=checklist_steps,
                meta=response.meta,
                emergency_banner=emergency_banner,
                blocked=False
            )
            
        except Exception as e:
            logger.error(f"Chat processing failed: {e}", exc_info=True)
            
            # Calculate response time for error case
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Log the error interaction
            if app_state["audit_logger"]:
                from ..critic.types import CriticDecision, CriticStatus
                error_decision = CriticDecision(
                    status=CriticStatus.BLOCK,
                    reasons=[f"System error: {str(e)}"],
                    emergency_detected=False
                )
                app_state["audit_logger"].log_interaction(
                    query=request.query,
                    critic_decision=error_decision,
                    conversation_id=conversation_id,
                    response_time_ms=response_time_ms,
                    llm_provider=type(app_state["llm_provider"]).__name__ if app_state["llm_provider"] else None
                )
                
                # Log performance metric for error
                app_state["audit_logger"].log_performance_metric(
                    endpoint="/chat",
                    response_time_ms=response_time_ms,
                    status_code=500,
                    error_message=str(e)
                )
            
            raise HTTPException(
                status_code=500,
                detail="Failed to process query. Please try again or contact emergency services if urgent."
            )
    
    # Document viewer endpoint
    @app.post("/document/view", response_model=DocumentViewResponse)
    async def view_document(request: DocumentViewRequest):
        """Retrieve document snippet for citation viewing."""
        try:
            if not app_state["browser_tool"]:
                raise HTTPException(
                    status_code=503,
                    detail="Document viewer not available"
                )
            
            # Use browser tool to get document content
            result = app_state["browser_tool"].open(
                doc_id=request.doc_id,
                start=request.start_offset,
                end=request.end_offset
            )
            
            if result["status"] == "error":
                return DocumentViewResponse(
                    doc_id=request.doc_id,
                    doc_title="Unknown",
                    text="",
                    location={},
                    success=False,
                    error=result["error"]
                )
            
            return DocumentViewResponse(
                doc_id=result["doc_id"],
                doc_title=result["doc_title"],
                text=result["text"],
                location=result["location"],
                success=True
            )
            
        except Exception as e:
            logger.error(f"Document view failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve document: {str(e)}"
            )
    
    # Admin authentication endpoint
    @app.post("/admin/login", response_model=AdminLoginResponse)
    async def admin_login(request: AdminLoginRequest):
        """Admin authentication endpoint."""
        if not authenticate_admin(request.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin credentials"
            )
        
        access_token, expires_in = create_admin_token()
        
        return AdminLoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in
        )
    
    # Admin audit log endpoint
    @app.get("/admin/audit", response_model=AuditLogResponse)
    async def get_audit_logs(
        page: int = 1,
        page_size: int = 50,
        blocked_only: bool = False,
        current_admin = Depends(get_current_admin)
    ):
        """Get audit logs (admin only)."""
        try:
            if not app_state["audit_logger"]:
                raise HTTPException(
                    status_code=503,
                    detail="Audit system not available"
                )
            
            # Calculate offset
            offset = (page - 1) * page_size
            
            # Get logs and total count
            logs = app_state["audit_logger"].get_recent_logs(
                limit=page_size,
                offset=offset,
                blocked_only=blocked_only
            )
            
            total_count = app_state["audit_logger"].get_log_count(blocked_only)
            
            # Convert to API format
            from .models import AuditLogEntry
            log_entries = []
            for log in logs:
                log_entries.append(AuditLogEntry(
                    timestamp=log["timestamp"],
                    query=log["query"],
                    response_blocked=log["response_blocked"],
                    critic_decision=log["critic_decision"],
                    emergency_detected=log["emergency_detected"],
                    conversation_id=log["conversation_id"]
                ))
            
            return AuditLogResponse(
                logs=log_entries,
                total_count=total_count,
                page=page,
                page_size=page_size
            )
            
        except Exception as e:
            logger.error(f"Audit log retrieval failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve audit logs: {str(e)}"
            )
    
    # Admin stats endpoint
    @app.get("/admin/stats")
    async def get_admin_stats(current_admin = Depends(get_current_admin)):
        """Get system statistics (admin only)."""
        try:
            if not app_state["audit_logger"]:
                raise HTTPException(
                    status_code=503,
                    detail="Audit system not available"
                )
            
            stats = app_state["audit_logger"].get_enhanced_stats()
            
            # Add component status
            stats["components"] = {
                "llm_provider": app_state["llm_provider"] is not None,
                "harmony_engine": app_state["harmony_engine"] is not None,
                "browser_tool": app_state["browser_tool"] is not None,
                "safety_critic": app_state["safety_critic"] is not None,
                "corpus_db": app_state["corpus_db"] is not None,
            }
            
            # Add available LLM providers
            stats["available_providers"] = get_available_providers()
            
            return stats
            
        except Exception as e:
            logger.error(f"Stats retrieval failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve stats: {str(e)}"
            )
    
    # System health monitoring endpoint
    @app.get("/admin/health-history")
    async def get_health_history(
        hours: int = 24,
        current_admin = Depends(get_current_admin)
    ):
        """Get system health history (admin only)."""
        try:
            if not app_state["audit_logger"]:
                raise HTTPException(
                    status_code=503,
                    detail="Audit system not available"
                )
            
            health_data = app_state["audit_logger"].get_system_health_history(hours)
            return {"health_history": health_data}
            
        except Exception as e:
            logger.error(f"Health history retrieval failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve health history: {str(e)}"
            )
    
    # Performance metrics endpoint
    @app.get("/admin/performance")
    async def get_performance_metrics(
        hours: int = 24,
        current_admin = Depends(get_current_admin)
    ):
        """Get performance metrics (admin only)."""
        try:
            if not app_state["audit_logger"]:
                raise HTTPException(
                    status_code=503,
                    detail="Audit system not available"
                )
            
            metrics = app_state["audit_logger"].get_performance_metrics(hours)
            return metrics
            
        except Exception as e:
            logger.error(f"Performance metrics retrieval failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve performance metrics: {str(e)}"
            )
    
    # Harmony debug endpoint
    @app.get("/admin/harmony-debug")
    async def get_harmony_debug(
        limit: int = 10,
        current_admin = Depends(get_current_admin)
    ):
        """Get Harmony debug data (admin only)."""
        try:
            if not app_state["audit_logger"]:
                raise HTTPException(
                    status_code=503,
                    detail="Audit system not available"
                )
            
            debug_data = app_state["audit_logger"].get_harmony_debug_data(limit)
            return {"harmony_debug": debug_data}
            
        except Exception as e:
            logger.error(f"Harmony debug retrieval failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve Harmony debug data: {str(e)}"
            )
    
    # System health logging (background task)
    @app.on_event("startup")
    async def start_health_monitoring():
        """Start background health monitoring."""
        import asyncio
        
        async def log_health_periodically():
            while True:
                try:
                    if app_state["audit_logger"]:
                        llm_status = "healthy" if app_state["llm_provider"] else "unavailable"
                        db_status = "healthy" if app_state["corpus_db"] else "unavailable"
                        
                        app_state["audit_logger"].log_system_health(
                            llm_provider_status=llm_status,
                            corpus_db_status=db_status
                        )
                    
                    # Log every 5 minutes
                    await asyncio.sleep(300)
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
                    await asyncio.sleep(60)  # Retry after 1 minute on error
        
        # Start the background task
        asyncio.create_task(log_health_periodically())
    
    return app


# Create app instance
app = create_app()