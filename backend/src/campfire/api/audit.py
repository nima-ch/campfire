"""
Audit logging system for tracking safety critic decisions and user interactions.
"""

import json
import sqlite3
from datetime import datetime
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
                    response_blocked INTEGER NOT NULL,
                    critic_decision TEXT NOT NULL,
                    emergency_detected INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for efficient querying
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON audit_logs(timestamp DESC)
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
        conversation_id: Optional[str] = None
    ):
        """Log a user interaction and safety critic decision.
        
        Args:
            query: User's original query
            critic_decision: Safety critic's decision
            conversation_id: Optional conversation identifier
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Serialize critic decision
        decision_data = {
            "status": critic_decision.status.value,
            "reasons": critic_decision.reasons,
            "fixes": critic_decision.fixes,
            "emergency_detected": critic_decision.emergency_detected,
            "requires_emergency_banner": critic_decision.requires_emergency_banner
        }
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_logs (
                    timestamp, conversation_id, query, response_blocked,
                    critic_decision, emergency_detected
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                conversation_id,
                query,
                1 if critic_decision.status.value == "BLOCK" else 0,
                json.dumps(decision_data),
                1 if critic_decision.emergency_detected else 0
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
            
            logs.append({
                "id": row["id"],
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "conversation_id": row["conversation_id"],
                "query": row["query"],
                "response_blocked": bool(row["response_blocked"]),
                "critic_decision": critic_decision,
                "emergency_detected": bool(row["emergency_detected"]),
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
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old audit log entries.
        
        Args:
            days_to_keep: Number of days of logs to retain
        """
        with self._get_connection() as conn:
            conn.execute("""
                DELETE FROM audit_logs 
                WHERE datetime(timestamp) < datetime('now', '-{} days')
            """.format(days_to_keep))
            conn.commit()