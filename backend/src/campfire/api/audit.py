"""
Audit logging system for tracking safety critic decisions and user interactions.
"""

import json
import sqlite3
import psutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from ..critic.types import CriticDecision


class AuditLogger:
    """Audit logger for tracking safety decisions and user interactions."""
    
    def __init__(self, db_path: str | Path):
        """Initialize audit logger with SQLite database.
        
        Args:
            db_path: Path to audit log database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize audit log database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    conversation_id TEXT,
                    query TEXT NOT NULL,
                    query_hash TEXT,
                    response_blocked INTEGER NOT NULL,
                    critic_decision TEXT NOT NULL,
                    emergency_detected INTEGER NOT NULL,
                    response_time_ms INTEGER,
                    llm_provider TEXT,
                    harmony_tokens_used INTEGER,
                    harmony_debug_data TEXT,
                    system_metrics TEXT,
                    user_agent TEXT,
                    ip_address TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create system health monitoring table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    memory_used_mb REAL,
                    disk_usage_percent REAL,
                    active_connections INTEGER,
                    llm_provider_status TEXT,
                    corpus_db_status TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create performance metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    response_time_ms INTEGER NOT NULL,
                    status_code INTEGER NOT NULL,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient querying
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON audit_logs(timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_blocked 
                ON audit_logs(response_blocked, timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_health_timestamp 
                ON system_health(timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_timestamp 
                ON performance_metrics(timestamp DESC)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def log_interaction(
        self,
        query: str,
        critic_decision: CriticDecision,
        conversation_id: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        llm_provider: Optional[str] = None,
        harmony_tokens_used: Optional[int] = None,
        harmony_debug_data: Optional[Dict[str, Any]] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log a user interaction and safety critic decision.
        
        Args:
            query: User's original query
            critic_decision: Safety critic's decision
            conversation_id: Optional conversation identifier
            response_time_ms: Response time in milliseconds
            llm_provider: LLM provider used
            harmony_tokens_used: Number of Harmony tokens used
            harmony_debug_data: Debug data from Harmony engine
            user_agent: User agent string
            ip_address: Client IP address
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Generate query hash for deduplication analysis
        import hashlib
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        # Serialize critic decision
        decision_data = {
            "status": critic_decision.status.value,
            "reasons": critic_decision.reasons,
            "fixes": critic_decision.fixes,
            "emergency_detected": critic_decision.emergency_detected,
            "requires_emergency_banner": critic_decision.requires_emergency_banner,
            "timestamp": timestamp
        }
        
        # Collect system metrics
        system_metrics = self._collect_system_metrics()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_logs (
                    timestamp, conversation_id, query, query_hash, response_blocked,
                    critic_decision, emergency_detected, response_time_ms,
                    llm_provider, harmony_tokens_used, harmony_debug_data,
                    system_metrics, user_agent, ip_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                conversation_id,
                query,
                query_hash,
                1 if critic_decision.status.value == "BLOCK" else 0,
                json.dumps(decision_data),
                1 if critic_decision.emergency_detected else 0,
                response_time_ms,
                llm_provider,
                harmony_tokens_used,
                json.dumps(harmony_debug_data) if harmony_debug_data else None,
                json.dumps(system_metrics),
                user_agent,
                ip_address
            ))
            conn.commit()
    
    def get_recent_logs(
        self, 
        limit: int = 50, 
        offset: int = 0,
        blocked_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get recent audit log entries.
        
        Args:
            limit: Maximum number of entries to return
            offset: Number of entries to skip
            blocked_only: If True, only return blocked responses
            
        Returns:
            List of audit log entries
        """
        query = """
            SELECT * FROM audit_logs 
            WHERE 1=1
        """
        params = []
        
        if blocked_only:
            query += " AND response_blocked = 1"
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        logs = []
        for row in rows:
            # Parse critic decision JSON
            try:
                critic_decision = json.loads(row["critic_decision"])
            except (json.JSONDecodeError, TypeError):
                critic_decision = {"status": "UNKNOWN", "reasons": []}
            
            # Parse system metrics JSON
            try:
                system_metrics = json.loads(row["system_metrics"]) if row["system_metrics"] else None
            except (json.JSONDecodeError, TypeError):
                system_metrics = None
            
            logs.append({
                "id": row["id"],
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "conversation_id": row["conversation_id"],
                "query": row["query"],
                "query_hash": row["query_hash"],
                "response_blocked": bool(row["response_blocked"]),
                "critic_decision": critic_decision,
                "emergency_detected": bool(row["emergency_detected"]),
                "response_time_ms": row["response_time_ms"],
                "llm_provider": row["llm_provider"],
                "harmony_tokens_used": row["harmony_tokens_used"],
                "system_metrics": system_metrics,
                "user_agent": row["user_agent"],
                "ip_address": row["ip_address"],
                "created_at": row["created_at"]
            })
        
        return logs
    
    def get_log_count(self, blocked_only: bool = False) -> int:
        """Get total count of audit log entries.
        
        Args:
            blocked_only: If True, only count blocked responses
            
        Returns:
            Total number of log entries
        """
        query = "SELECT COUNT(*) as count FROM audit_logs"
        params = []
        
        if blocked_only:
            query += " WHERE response_blocked = 1"
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            result = cursor.fetchone()
        
        return result["count"] if result else 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics.
        
        Returns:
            Dictionary with various statistics
        """
        with self._get_connection() as conn:
            # Total interactions
            total_cursor = conn.execute("SELECT COUNT(*) as count FROM audit_logs")
            total_count = total_cursor.fetchone()["count"]
            
            # Blocked interactions
            blocked_cursor = conn.execute(
                "SELECT COUNT(*) as count FROM audit_logs WHERE response_blocked = 1"
            )
            blocked_count = blocked_cursor.fetchone()["count"]
            
            # Emergency detections
            emergency_cursor = conn.execute(
                "SELECT COUNT(*) as count FROM audit_logs WHERE emergency_detected = 1"
            )
            emergency_count = emergency_cursor.fetchone()["count"]
            
            # Recent activity (last 24 hours)
            recent_cursor = conn.execute("""
                SELECT COUNT(*) as count FROM audit_logs 
                WHERE datetime(timestamp) > datetime('now', '-1 day')
            """)
            recent_count = recent_cursor.fetchone()["count"]
        
        return {
            "total_interactions": total_count,
            "blocked_responses": blocked_count,
            "emergency_detections": emergency_count,
            "recent_activity_24h": recent_count,
            "block_rate": blocked_count / total_count if total_count > 0 else 0,
            "emergency_rate": emergency_count / total_count if total_count > 0 else 0
        }
    
    def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics."""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_used_mb": psutil.virtual_memory().used / (1024 * 1024),
                "disk_usage_percent": psutil.disk_usage('/').percent,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
    
    def log_system_health(self, llm_provider_status: str = "unknown", corpus_db_status: str = "unknown"):
        """Log current system health metrics.
        
        Args:
            llm_provider_status: Status of LLM provider
            corpus_db_status: Status of corpus database
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        metrics = self._collect_system_metrics()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO system_health (
                    timestamp, cpu_percent, memory_percent, memory_used_mb,
                    disk_usage_percent, active_connections, llm_provider_status,
                    corpus_db_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                metrics.get("cpu_percent"),
                metrics.get("memory_percent"),
                metrics.get("memory_used_mb"),
                metrics.get("disk_usage_percent"),
                0,  # TODO: Track active connections
                llm_provider_status,
                corpus_db_status
            ))
            conn.commit()
    
    def log_performance_metric(
        self,
        endpoint: str,
        response_time_ms: int,
        status_code: int,
        error_message: Optional[str] = None
    ):
        """Log performance metrics for API endpoints.
        
        Args:
            endpoint: API endpoint path
            response_time_ms: Response time in milliseconds
            status_code: HTTP status code
            error_message: Optional error message
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO performance_metrics (
                    timestamp, endpoint, response_time_ms, status_code, error_message
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                timestamp,
                endpoint,
                response_time_ms,
                status_code,
                error_message
            ))
            conn.commit()
    
    def get_system_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get system health history for the specified time period.
        
        Args:
            hours: Number of hours of history to retrieve
            
        Returns:
            List of system health entries
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM system_health 
                WHERE datetime(timestamp) > datetime('now', '-{} hours')
                ORDER BY timestamp DESC
            """.format(hours))
            rows = cursor.fetchall()
        
        health_data = []
        for row in rows:
            health_data.append({
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "cpu_percent": row["cpu_percent"],
                "memory_percent": row["memory_percent"],
                "memory_used_mb": row["memory_used_mb"],
                "disk_usage_percent": row["disk_usage_percent"],
                "active_connections": row["active_connections"],
                "llm_provider_status": row["llm_provider_status"],
                "corpus_db_status": row["corpus_db_status"]
            })
        
        return health_data
    
    def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics for the specified time period.
        
        Args:
            hours: Number of hours of metrics to analyze
            
        Returns:
            Dictionary with performance statistics
        """
        with self._get_connection() as conn:
            # Average response times by endpoint
            cursor = conn.execute("""
                SELECT endpoint, 
                       AVG(response_time_ms) as avg_response_time,
                       MIN(response_time_ms) as min_response_time,
                       MAX(response_time_ms) as max_response_time,
                       COUNT(*) as request_count
                FROM performance_metrics 
                WHERE datetime(timestamp) > datetime('now', '-{} hours')
                GROUP BY endpoint
                ORDER BY avg_response_time DESC
            """.format(hours))
            endpoint_stats = cursor.fetchall()
            
            # Error rates
            error_cursor = conn.execute("""
                SELECT status_code, COUNT(*) as count
                FROM performance_metrics 
                WHERE datetime(timestamp) > datetime('now', '-{} hours')
                GROUP BY status_code
                ORDER BY count DESC
            """.format(hours))
            status_codes = error_cursor.fetchall()
        
        return {
            "endpoint_performance": [dict(row) for row in endpoint_stats],
            "status_code_distribution": [dict(row) for row in status_codes]
        }
    
    def get_harmony_debug_data(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent Harmony debug data for developer inspection.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of Harmony debug entries
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT timestamp, query, harmony_debug_data, harmony_tokens_used
                FROM audit_logs 
                WHERE harmony_debug_data IS NOT NULL
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        
        debug_entries = []
        for row in rows:
            try:
                debug_data = json.loads(row["harmony_debug_data"]) if row["harmony_debug_data"] else {}
            except (json.JSONDecodeError, TypeError):
                debug_data = {}
            
            debug_entries.append({
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "query": row["query"],
                "harmony_debug_data": debug_data,
                "harmony_tokens_used": row["harmony_tokens_used"]
            })
        
        return debug_entries
    
    def get_enhanced_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics.
        
        Returns:
            Dictionary with detailed statistics
        """
        base_stats = self.get_stats()
        
        with self._get_connection() as conn:
            # Query patterns analysis
            pattern_cursor = conn.execute("""
                SELECT query_hash, COUNT(*) as frequency, 
                       MAX(timestamp) as last_seen,
                       AVG(response_time_ms) as avg_response_time
                FROM audit_logs 
                WHERE query_hash IS NOT NULL
                GROUP BY query_hash
                HAVING frequency > 1
                ORDER BY frequency DESC
                LIMIT 10
            """)
            query_patterns = pattern_cursor.fetchall()
            
            # Provider usage statistics
            provider_cursor = conn.execute("""
                SELECT llm_provider, COUNT(*) as usage_count,
                       AVG(response_time_ms) as avg_response_time
                FROM audit_logs 
                WHERE llm_provider IS NOT NULL
                GROUP BY llm_provider
                ORDER BY usage_count DESC
            """)
            provider_stats = provider_cursor.fetchall()
            
            # Recent system health
            health_cursor = conn.execute("""
                SELECT AVG(cpu_percent) as avg_cpu,
                       AVG(memory_percent) as avg_memory,
                       AVG(disk_usage_percent) as avg_disk
                FROM system_health 
                WHERE datetime(timestamp) > datetime('now', '-1 hour')
            """)
            recent_health = health_cursor.fetchone()
        
        # Enhance base stats
        base_stats.update({
            "query_patterns": [dict(row) for row in query_patterns],
            "provider_usage": [dict(row) for row in provider_stats],
            "recent_system_health": dict(recent_health) if recent_health else {},
            "performance_metrics": self.get_performance_metrics(24)
        })
        
        return base_stats
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old audit log entries.
        
        Args:
            days_to_keep: Number of days of logs to retain
        """
        with self._get_connection() as conn:
            # Clean up audit logs
            conn.execute("""
                DELETE FROM audit_logs 
                WHERE datetime(timestamp) < datetime('now', '-{} days')
            """.format(days_to_keep))
            
            # Clean up system health logs (keep less history)
            conn.execute("""
                DELETE FROM system_health 
                WHERE datetime(timestamp) < datetime('now', '-{} days')
            """.format(min(days_to_keep, 7)))
            
            # Clean up performance metrics (keep less history)
            conn.execute("""
                DELETE FROM performance_metrics 
                WHERE datetime(timestamp) < datetime('now', '-{} days')
            """.format(min(days_to_keep, 7)))
            
            conn.commit()