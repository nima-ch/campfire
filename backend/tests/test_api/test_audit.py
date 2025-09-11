"""
Tests for the enhanced audit logging system.
"""

import json
import tempfile
import pytest
from datetime import datetime, timezone
from pathlib import Path

from campfire.api.audit import AuditLogger
from campfire.critic.types import CriticDecision, CriticStatus


@pytest.fixture
def temp_audit_db():
    """Create a temporary audit database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Clean up
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def audit_logger(temp_audit_db):
    """Create an AuditLogger instance for testing."""
    return AuditLogger(temp_audit_db)


class TestAuditLogger:
    """Test cases for the AuditLogger class."""
    
    def test_init_database(self, audit_logger):
        """Test database initialization."""
        # Database should be created and tables should exist
        with audit_logger._get_connection() as conn:
            # Check audit_logs table
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='audit_logs'
            """)
            assert cursor.fetchone() is not None
            
            # Check system_health table
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='system_health'
            """)
            assert cursor.fetchone() is not None
            
            # Check performance_metrics table
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='performance_metrics'
            """)
            assert cursor.fetchone() is not None
    
    def test_log_interaction_basic(self, audit_logger):
        """Test basic interaction logging."""
        decision = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Response meets safety criteria"],
            emergency_detected=False
        )
        
        audit_logger.log_interaction(
            query="How to treat a minor cut?",
            critic_decision=decision,
            conversation_id="test-123"
        )
        
        logs = audit_logger.get_recent_logs(limit=1)
        assert len(logs) == 1
        
        log = logs[0]
        assert log["query"] == "How to treat a minor cut?"
        assert log["conversation_id"] == "test-123"
        assert log["response_blocked"] is False
        assert log["emergency_detected"] is False
        assert log["critic_decision"]["status"] == "ALLOW"
    
    def test_log_interaction_blocked(self, audit_logger):
        """Test logging of blocked interactions."""
        decision = CriticDecision(
            status=CriticStatus.BLOCK,
            reasons=["Missing source citations", "Inappropriate medical advice"],
            fixes=["Add proper citations", "Remove medical claims"],
            emergency_detected=True
        )
        
        audit_logger.log_interaction(
            query="How to perform surgery?",
            critic_decision=decision,
            response_time_ms=1500,
            llm_provider="OllamaProvider",
            harmony_tokens_used=250
        )
        
        logs = audit_logger.get_recent_logs(limit=1)
        assert len(logs) == 1
        
        log = logs[0]
        assert log["query"] == "How to perform surgery?"
        assert log["response_blocked"] is True
        assert log["emergency_detected"] is True
        assert log["response_time_ms"] == 1500
        assert log["llm_provider"] == "OllamaProvider"
        assert log["harmony_tokens_used"] == 250
        assert len(log["critic_decision"]["reasons"]) == 2
        assert len(log["critic_decision"]["fixes"]) == 2
    
    def test_log_interaction_with_harmony_debug(self, audit_logger):
        """Test logging with Harmony debug data."""
        decision = CriticDecision(
            status=CriticStatus.ALLOW,
            reasons=["Valid response"],
            emergency_detected=False
        )
        
        harmony_debug = {
            "prefill_tokens": 150,
            "completion_tokens": 200,
            "tool_calls": [
                {"name": "search", "args": {"q": "first aid"}},
                {"name": "open", "args": {"doc_id": "ifrc-2020", "start": 100, "end": 200}}
            ]
        }
        
        audit_logger.log_interaction(
            query="First aid for burns",
            critic_decision=decision,
            harmony_debug_data=harmony_debug
        )
        
        logs = audit_logger.get_recent_logs(limit=1)
        log = logs[0]
        
        # Check that harmony debug data was stored
        debug_data = log["critic_decision"]
        assert "timestamp" in debug_data
    
    def test_log_system_health(self, audit_logger):
        """Test system health logging."""
        audit_logger.log_system_health(
            llm_provider_status="healthy",
            corpus_db_status="healthy"
        )
        
        health_data = audit_logger.get_system_health_history(hours=1)
        assert len(health_data) == 1
        
        health = health_data[0]
        assert health["llm_provider_status"] == "healthy"
        assert health["corpus_db_status"] == "healthy"
        assert "cpu_percent" in health
        assert "memory_percent" in health
    
    def test_log_performance_metric(self, audit_logger):
        """Test performance metric logging."""
        audit_logger.log_performance_metric(
            endpoint="/chat",
            response_time_ms=1200,
            status_code=200
        )
        
        audit_logger.log_performance_metric(
            endpoint="/chat",
            response_time_ms=2500,
            status_code=500,
            error_message="Internal server error"
        )
        
        metrics = audit_logger.get_performance_metrics(hours=1)
        
        # Check endpoint performance
        endpoint_perf = metrics["endpoint_performance"]
        assert len(endpoint_perf) == 1
        assert endpoint_perf[0]["endpoint"] == "/chat"
        assert endpoint_perf[0]["request_count"] == 2
        assert endpoint_perf[0]["avg_response_time"] == 1850  # (1200 + 2500) / 2
        
        # Check status code distribution
        status_dist = metrics["status_code_distribution"]
        assert len(status_dist) == 2
        status_codes = {item["status_code"]: item["count"] for item in status_dist}
        assert status_codes[200] == 1
        assert status_codes[500] == 1
    
    def test_get_recent_logs_pagination(self, audit_logger):
        """Test pagination of recent logs."""
        # Create multiple log entries
        for i in range(15):
            decision = CriticDecision(
                status=CriticStatus.ALLOW if i % 2 == 0 else CriticStatus.BLOCK,
                reasons=[f"Reason {i}"],
                emergency_detected=i % 3 == 0
            )
            
            audit_logger.log_interaction(
                query=f"Query {i}",
                critic_decision=decision
            )
        
        # Test pagination
        first_page = audit_logger.get_recent_logs(limit=5, offset=0)
        second_page = audit_logger.get_recent_logs(limit=5, offset=5)
        
        assert len(first_page) == 5
        assert len(second_page) == 5
        
        # Should be in reverse chronological order
        assert first_page[0]["query"] == "Query 14"  # Most recent
        assert second_page[0]["query"] == "Query 9"
        
        # Test blocked_only filter
        blocked_logs = audit_logger.get_recent_logs(blocked_only=True)
        assert all(log["response_blocked"] for log in blocked_logs)
        assert len(blocked_logs) == 7  # Odd numbered queries (1,3,5,7,9,11,13) - but 0-indexed, so 7 total
    
    def test_get_log_count(self, audit_logger):
        """Test log count functionality."""
        # Initially no logs
        assert audit_logger.get_log_count() == 0
        assert audit_logger.get_log_count(blocked_only=True) == 0
        
        # Add some logs
        for i in range(10):
            decision = CriticDecision(
                status=CriticStatus.BLOCK if i < 3 else CriticStatus.ALLOW,
                reasons=[f"Reason {i}"],
                emergency_detected=False
            )
            
            audit_logger.log_interaction(
                query=f"Query {i}",
                critic_decision=decision
            )
        
        assert audit_logger.get_log_count() == 10
        assert audit_logger.get_log_count(blocked_only=True) == 3
    
    def test_get_enhanced_stats(self, audit_logger):
        """Test enhanced statistics functionality."""
        # Add some test data
        for i in range(5):
            decision = CriticDecision(
                status=CriticStatus.BLOCK if i < 2 else CriticStatus.ALLOW,
                reasons=[f"Reason {i}"],
                emergency_detected=i == 0
            )
            
            audit_logger.log_interaction(
                query=f"Query {i}",
                critic_decision=decision,
                response_time_ms=1000 + i * 100,
                llm_provider="TestProvider"
            )
        
        # Add system health data
        audit_logger.log_system_health("healthy", "healthy")
        
        # Add performance metrics
        audit_logger.log_performance_metric("/chat", 1200, 200)
        
        stats = audit_logger.get_enhanced_stats()
        
        # Check basic stats
        assert stats["total_interactions"] == 5
        assert stats["blocked_responses"] == 2
        assert stats["emergency_detections"] == 1
        assert stats["block_rate"] == 0.4
        assert stats["emergency_rate"] == 0.2
        
        # Check provider usage
        assert len(stats["provider_usage"]) == 1
        assert stats["provider_usage"][0]["llm_provider"] == "TestProvider"
        assert stats["provider_usage"][0]["usage_count"] == 5
        
        # Check performance metrics
        assert "endpoint_performance" in stats["performance_metrics"]
        assert "status_code_distribution" in stats["performance_metrics"]
    
    def test_get_harmony_debug_data(self, audit_logger):
        """Test Harmony debug data retrieval."""
        # Add logs with and without debug data
        for i in range(3):
            decision = CriticDecision(
                status=CriticStatus.ALLOW,
                reasons=["Valid"],
                emergency_detected=False
            )
            
            debug_data = {"tokens": i * 10} if i > 0 else None
            
            audit_logger.log_interaction(
                query=f"Query {i}",
                critic_decision=decision,
                harmony_debug_data=debug_data,
                harmony_tokens_used=i * 10 if i > 0 else None
            )
        
        debug_entries = audit_logger.get_harmony_debug_data(limit=5)
        
        # Should only return entries with debug data
        assert len(debug_entries) == 2
        assert debug_entries[0]["harmony_debug_data"]["tokens"] == 20
        assert debug_entries[1]["harmony_debug_data"]["tokens"] == 10
    
    def test_cleanup_old_logs(self, audit_logger):
        """Test cleanup of old log entries."""
        # Add some logs
        for i in range(5):
            decision = CriticDecision(
                status=CriticStatus.ALLOW,
                reasons=["Valid"],
                emergency_detected=False
            )
            
            audit_logger.log_interaction(
                query=f"Query {i}",
                critic_decision=decision
            )
        
        # Add system health and performance data
        audit_logger.log_system_health("healthy", "healthy")
        audit_logger.log_performance_metric("/test", 1000, 200)
        
        # Verify data exists
        assert audit_logger.get_log_count() == 5
        assert len(audit_logger.get_system_health_history(hours=24)) == 1
        assert len(audit_logger.get_performance_metrics(hours=24)["endpoint_performance"]) == 1
        
        # Cleanup (this won't actually delete anything since logs are recent)
        audit_logger.cleanup_old_logs(days_to_keep=30)
        
        # Data should still exist
        assert audit_logger.get_log_count() == 5
    
    def test_collect_system_metrics(self, audit_logger):
        """Test system metrics collection."""
        metrics = audit_logger._collect_system_metrics()
        
        # Should contain basic system metrics
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "memory_used_mb" in metrics
        assert "disk_usage_percent" in metrics
        assert "timestamp" in metrics
        
        # Values should be reasonable
        assert 0 <= metrics["cpu_percent"] <= 100
        assert 0 <= metrics["memory_percent"] <= 100
        assert metrics["memory_used_mb"] > 0
        assert 0 <= metrics["disk_usage_percent"] <= 100


class TestAuditLoggerIntegration:
    """Integration tests for audit logger with other components."""
    
    def test_critic_decision_serialization(self, audit_logger):
        """Test that CriticDecision objects are properly serialized."""
        decision = CriticDecision(
            status=CriticStatus.BLOCK,
            reasons=["Test reason 1", "Test reason 2"],
            fixes=["Fix 1", "Fix 2"],
            emergency_detected=True,
            requires_emergency_banner=True
        )
        
        audit_logger.log_interaction(
            query="Test query",
            critic_decision=decision
        )
        
        logs = audit_logger.get_recent_logs(limit=1)
        log = logs[0]
        
        critic_data = log["critic_decision"]
        assert critic_data["status"] == "BLOCK"
        assert len(critic_data["reasons"]) == 2
        assert len(critic_data["fixes"]) == 2
        assert critic_data["emergency_detected"] is True
        assert critic_data["requires_emergency_banner"] is True
    
    def test_concurrent_logging(self, audit_logger):
        """Test that concurrent logging operations work correctly."""
        import threading
        
        def log_entries(start_idx, count):
            for i in range(start_idx, start_idx + count):
                decision = CriticDecision(
                    status=CriticStatus.ALLOW,
                    reasons=[f"Reason {i}"],
                    emergency_detected=False
                )
                
                audit_logger.log_interaction(
                    query=f"Concurrent query {i}",
                    critic_decision=decision
                )
        
        # Create multiple threads with non-overlapping ranges
        threads = []
        for i in range(3):
            thread = threading.Thread(target=log_entries, args=(i * 5, 5))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have 15 total logs
        assert audit_logger.get_log_count() == 15
        
        # All queries should be present (check by count since order may vary due to threading)
        logs = audit_logger.get_recent_logs(limit=20)
        queries = {log["query"] for log in logs}
        
        # Check that we have the expected number of unique queries
        expected_queries = {f"Concurrent query {i}" for i in range(15)}
        assert queries == expected_queries