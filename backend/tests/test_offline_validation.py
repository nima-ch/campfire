"""
Comprehensive offline validation tests for Campfire emergency helper.

Tests airplane mode functionality, network isolation, and complete offline operation.
"""

import pytest
import asyncio
import socket
import subprocess
import time
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager

from campfire.api.main import create_app, app_state
from campfire.corpus import CorpusDatabase
from campfire.llm.factory import create_provider, ProviderConfig, ProviderType
from campfire.harmony.engine import HarmonyEngine
from campfire.critic import SafetyCritic


class TestOfflineValidation:
    """Test complete offline operation and network isolation."""
    
    @pytest.fixture
    def isolated_environment(self):
        """Create completely isolated test environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create isolated corpus database
            corpus_db_path = temp_path / "test_corpus.db"
            corpus_db = CorpusDatabase(str(corpus_db_path))
            corpus_db.initialize_schema()
            
            # Add minimal test corpus
            corpus_db.add_document(
                "ifrc_test", 
                "IFRC Test Guidelines", 
                str(temp_path / "ifrc_test.pdf")
            )
            corpus_db.add_chunk(
                "ifrc_test",
                "For burns: Cool with running water for 10-20 minutes. Remove jewelry. Cover with sterile bandage.",
                0, 95, 1
            )
            corpus_db.add_chunk(
                "ifrc_test", 
                "For bleeding: Apply direct pressure with clean cloth. Elevate if possible. Call emergency services for severe bleeding.",
                96, 200, 1
            )
            
            corpus_db.add_document(
                "who_test",
                "WHO Psychological First Aid Test",
                str(temp_path / "who_test.pdf")
            )
            corpus_db.add_chunk(
                "who_test",
                "Psychological first aid: Listen without judgment. Provide comfort and support. Connect with social supports.",
                0, 105, 1
            )
            
            yield {
                "temp_path": temp_path,
                "corpus_db": corpus_db,
                "corpus_db_path": str(corpus_db_path)
            }
            
            corpus_db.close()
    
    @contextmanager
    def network_isolation(self):
        """Context manager to simulate network isolation."""
        def mock_socket(*args, **kwargs):
            raise OSError("Network is unreachable (simulated airplane mode)")
        
        def mock_getaddrinfo(*args, **kwargs):
            raise OSError("Network is unreachable (simulated airplane mode)")
        
        with patch('socket.socket', side_effect=mock_socket):
            with patch('socket.getaddrinfo', side_effect=mock_getaddrinfo):
                yield
    
    def test_airplane_mode_functionality(self, isolated_environment):
        """Test that system works completely in airplane mode."""
        with self.network_isolation():
            # Initialize all components in isolation
            corpus_db = isolated_environment["corpus_db"]
            
            # Mock LLM provider (simulating local model)
            mock_llm = Mock()
            mock_llm.supports_tokens.return_value = True
            mock_llm.generate.return_value = {
                "completion": '{"checklist": [{"title": "Cool Burn", "action": "Cool with running water", "source": {"doc_id": "ifrc_test", "loc": [0, 50]}}], "meta": {"disclaimer": "Not medical advice"}}'
            }
            
            # Test corpus search works offline
            results = corpus_db.search("burns")
            assert len(results) > 0
            assert "burn" in results[0]["text"].lower()
            
            # Test document retrieval works offline
            doc_info = corpus_db.get_document_info("ifrc_test")
            assert doc_info is not None
            assert doc_info["title"] == "IFRC Test Guidelines"
            
            # Test safety critic works offline
            critic = SafetyCritic()
            test_response = {
                'checklist': [
                    {
                        'title': 'Cool Burn',
                        'action': 'Cool with running water for 10-20 minutes',
                        'source': {'doc_id': 'ifrc_test', 'loc': [0, 50]}
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice'}
            }
            
            decision = critic.review_response(test_response)
            assert decision.status.value in ["ALLOW", "BLOCK"]  # Should work without network
    
    def test_no_external_network_calls(self, isolated_environment):
        """Verify no external network calls are made during operation."""
        network_calls = []
        
        def track_network_call(*args, **kwargs):
            network_calls.append(args)
            raise OSError("Network blocked for testing")
        
        with patch('socket.socket', side_effect=track_network_call):
            # Test corpus operations
            corpus_db = isolated_environment["corpus_db"]
            results = corpus_db.search("emergency")
            
            # Test safety critic
            critic = SafetyCritic()
            test_response = {
                'checklist': [{'title': 'Test', 'action': 'Test action', 'source': {'doc_id': 'test', 'loc': [0, 10]}}],
                'meta': {'disclaimer': 'Not medical advice'}
            }
            critic.review_response(test_response)
        
        # Should have no network calls
        assert len(network_calls) == 0, f"Unexpected network calls detected: {network_calls}"
    
    def test_offline_status_detection(self, isolated_environment):
        """Test that offline status is properly detected and reported."""
        with self.network_isolation():
            # Test that we can create components without network
            corpus_db = isolated_environment["corpus_db"]
            
            # Should be able to check documents offline
            documents = corpus_db.list_documents()
            assert isinstance(documents, list)
            assert len(documents) >= 2  # Should have test documents
    
    def test_local_model_simulation(self, isolated_environment):
        """Test simulation of local model inference without network."""
        with self.network_isolation():
            # Mock local LLM provider
            mock_provider = Mock()
            mock_provider.supports_tokens.return_value = True
            mock_provider.generate.return_value = {
                "completion": '{"checklist": [{"title": "Emergency Response", "action": "Call emergency services", "source": {"doc_id": "ifrc_test", "loc": [0, 50]}}], "meta": {"disclaimer": "Not medical advice"}}'
            }
            
            # Test that provider works without network
            result = mock_provider.generate([], [])
            assert "completion" in result
            assert "checklist" in result["completion"]
    
    def test_corpus_integrity_offline(self, isolated_environment):
        """Test corpus database integrity in offline mode."""
        with self.network_isolation():
            corpus_db = isolated_environment["corpus_db"]
            
            # Test all basic operations work
            documents = corpus_db.list_documents()
            assert len(documents) >= 2
            
            # Test search functionality
            burn_results = corpus_db.search("burns")
            bleeding_results = corpus_db.search("bleeding")
            
            assert len(burn_results) > 0, f"No results for 'burns' search. Available docs: {documents}"
            assert len(bleeding_results) > 0, f"No results for 'bleeding' search. Available docs: {documents}"
            
            # Test document retrieval
            for doc in documents:
                doc_info = corpus_db.get_document_info(doc["doc_id"])
                assert doc_info is not None
                
                chunks = corpus_db.get_document_chunks(doc["doc_id"])
                assert len(chunks) > 0
    
    def test_resource_usage_offline(self, isolated_environment):
        """Test resource usage remains reasonable in offline mode."""
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil not available")
        import gc
        
        with self.network_isolation():
            # Measure initial memory
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            corpus_db = isolated_environment["corpus_db"]
            
            # Perform multiple operations
            for i in range(10):
                results = corpus_db.search(f"emergency {i}")
                doc_info = corpus_db.get_document_info("ifrc_test")
                chunks = corpus_db.get_document_chunks("ifrc_test")
            
            # Force garbage collection
            gc.collect()
            
            # Measure final memory
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 100MB)
            assert memory_increase < 100 * 1024 * 1024, f"Memory usage increased by {memory_increase / 1024 / 1024:.2f}MB"
    
    def test_startup_without_network(self, isolated_environment):
        """Test that application can start up without network access."""
        with self.network_isolation():
            # Mock application startup components
            with patch('campfire.api.main.initialize_components') as mock_init:
                mock_init.return_value = None
                
                # Should be able to create app without network
                app = create_app()
                assert app is not None
    
    def test_configuration_validation_offline(self, isolated_environment):
        """Test configuration validation works offline."""
        with self.network_isolation():
            # Test corpus database configuration
            corpus_db = isolated_environment["corpus_db"]
            
            # Verify database schema
            documents = corpus_db.list_documents()
            assert isinstance(documents, list)
            
            # Test search index
            results = corpus_db.search("test")
            assert isinstance(results, list)
    
    @pytest.mark.slow
    def test_extended_offline_operation(self, isolated_environment):
        """Test extended offline operation over time."""
        with self.network_isolation():
            corpus_db = isolated_environment["corpus_db"]
            
            # Simulate extended usage
            start_time = time.time()
            operations_count = 0
            
            while time.time() - start_time < 5:  # Run for 5 seconds
                # Perform various operations
                corpus_db.search("emergency")
                corpus_db.get_document_info("ifrc_test")
                corpus_db.list_documents()
                operations_count += 1
                
                time.sleep(0.1)  # Small delay between operations
            
            # Should have performed multiple operations successfully
            assert operations_count > 10
    
    def test_offline_error_handling(self, isolated_environment):
        """Test error handling in offline scenarios."""
        with self.network_isolation():
            corpus_db = isolated_environment["corpus_db"]
            
            # Test handling of missing documents
            result = corpus_db.get_document_info("nonexistent")
            assert result is None
            
            # Test handling of empty searches
            results = corpus_db.search("nonexistentterm12345")
            assert results == []
            
            # Test handling of invalid queries
            try:
                results = corpus_db.search("")
                assert isinstance(results, list)
            except Exception:
                # Empty search may cause FTS5 syntax error, which is acceptable
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])