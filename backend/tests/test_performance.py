"""
Performance tests for Campfire emergency helper.

Tests response time, resource usage, and system performance under various conditions.
"""

import pytest
import time
import threading
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from campfire.api.main import create_app, app_state
from campfire.corpus import CorpusDatabase
from campfire.harmony.browser import LocalBrowserTool
from campfire.critic import SafetyCritic
from campfire.critic.types import ChecklistResponse, ChecklistStep


@pytest.fixture
def performance_test_setup():
    """Set up performance testing environment."""
    # Create temporary corpus database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = CorpusDatabase(db_path)
    db.initialize_schema()
    
    # Add substantial test content for performance testing
    documents = [
        ("ifrc_burns", "IFRC Burn Treatment Guidelines"),
        ("ifrc_bleeding", "IFRC Bleeding Control Guidelines"),
        ("ifrc_cpr", "IFRC CPR Guidelines"),
        ("who_pfa", "WHO Psychological First Aid"),
        ("who_emergency", "WHO Emergency Response")
    ]
    
    for doc_id, title in documents:
        db.add_document(doc_id, title, f"/test/{doc_id}.pdf")
        
        # Add multiple chunks per document
        for i in range(10):
            start_offset = i * 100
            end_offset = (i + 1) * 100 - 1
            content = f"Emergency response content for {doc_id} chunk {i}. " * 5
            db.add_chunk(doc_id, content, start_offset, end_offset, i // 3 + 1)
    
    browser_tool = LocalBrowserTool(db_path)
    critic = SafetyCritic()
    
    yield {
        "db": db,
        "browser_tool": browser_tool,
        "critic": critic,
        "db_path": db_path
    }
    
    db.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def performance_test_client(performance_test_setup):
    """Create test client for performance testing."""
    with patch.multiple(
        'campfire.api.main',
        initialize_components=AsyncMock(),
        cleanup_components=AsyncMock()
    ):
        # Mock components with performance test setup
        mock_llm = Mock()
        mock_llm.supports_tokens.return_value = True
        mock_llm.generate.return_value = {
            "completion": '{"checklist": [{"title": "Emergency Response", "action": "Take appropriate action", "source": {"doc_id": "ifrc_burns", "loc": [0, 50]}}], "meta": {"disclaimer": "Not medical advice"}}'
        }
        app_state["llm_provider"] = mock_llm
        
        app_state["browser_tool"] = performance_test_setup["browser_tool"]
        
        mock_harmony = Mock()
        mock_harmony.process_query = AsyncMock(return_value=ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Emergency Response",
                    action="Take appropriate emergency action",
                    source={"doc_id": "ifrc_burns", "loc": [0, 50]}
                )
            ],
            meta={"disclaimer": "Not medical advice"}
        ))
        app_state["harmony_engine"] = mock_harmony
        
        app_state["safety_critic"] = performance_test_setup["critic"]
        
        mock_audit = Mock()
        mock_audit.log_interaction = Mock()
        app_state["audit_logger"] = mock_audit
        
        app_state["corpus_db"] = performance_test_setup["db"]
        
        app = create_app()
        client = TestClient(app)
        
        yield {
            "client": client,
            "setup": performance_test_setup,
            "mocks": {
                "llm": mock_llm,
                "harmony": mock_harmony,
                "audit": mock_audit
            }
        }


class TestPerformance:
    """Test system performance under various conditions."""
    
    def test_response_time_target(self, performance_test_client):
        """Test that responses meet the <10 second target."""
        client = performance_test_client["client"]
        
        test_queries = [
            "What should I do for a burn?",
            "Someone is bleeding heavily",
            "How to help someone who is choking?",
            "Person is unconscious, what to do?",
            "Treating a sprained ankle"
        ]
        
        response_times = []
        
        for query in test_queries:
            start_time = time.time()
            
            response = client.post("/chat", json={
                "query": query,
                "conversation_id": f"perf-test-{len(response_times)}"
            })
            
            end_time = time.time()
            response_time = end_time - start_time
            response_times.append(response_time)
            
            # Verify response is successful
            assert response.status_code == 200
            data = response.json()
            assert "checklist" in data
            
            # Each response should be under 10 seconds
            assert response_time < 10.0, f"Response time {response_time:.2f}s exceeds 10s target for query: {query}"
        
        # Average response time should be reasonable
        avg_response_time = sum(response_times) / len(response_times)
        assert avg_response_time < 5.0, f"Average response time {avg_response_time:.2f}s is too high"
        
        print(f"Response times: {[f'{t:.2f}s' for t in response_times]}")
        print(f"Average response time: {avg_response_time:.2f}s")
    
    def test_corpus_search_performance(self, performance_test_setup):
        """Test corpus search performance."""
        browser_tool = performance_test_setup["browser_tool"]
        
        search_queries = [
            "emergency response",
            "burn treatment",
            "bleeding control",
            "psychological first aid",
            "cpr guidelines",
            "unconscious person",
            "chest pain",
            "choking victim"
        ]
        
        search_times = []
        
        for query in search_queries:
            start_time = time.time()
            search_response = browser_tool.search(query)
            end_time = time.time()
            
            search_time = end_time - start_time
            search_times.append(search_time)
            
            # Verify results
            assert search_response["status"] == "success"
            assert search_response["total_results"] >= 0
            
            # Each search should complete quickly
            assert search_time < 1.0, f"Search time {search_time:.3f}s too slow for query: {query}"
        
        avg_search_time = sum(search_times) / len(search_times)
        assert avg_search_time < 0.5, f"Average search time {avg_search_time:.3f}s is too high"
        
        print(f"Search times: {[f'{t:.3f}s' for t in search_times]}")
        print(f"Average search time: {avg_search_time:.3f}s")
    
    def test_document_retrieval_performance(self, performance_test_setup):
        """Test document retrieval performance."""
        browser_tool = performance_test_setup["browser_tool"]
        
        # Test multiple document retrievals
        retrieval_times = []
        
        for doc_id in ["ifrc_burns", "ifrc_bleeding", "ifrc_cpr", "who_pfa"]:
            for i in range(5):  # 5 retrievals per document
                start_offset = i * 100
                end_offset = (i + 1) * 100 - 1
                
                start_time = time.time()
                result = browser_tool.open(doc_id, start_offset, end_offset)
                end_time = time.time()
                
                retrieval_time = end_time - start_time
                retrieval_times.append(retrieval_time)
                
                # Verify successful retrieval
                assert result["status"] == "success"
                assert len(result["text"]) > 0
                
                # Each retrieval should be fast
                assert retrieval_time < 0.5, f"Retrieval time {retrieval_time:.3f}s too slow"
        
        avg_retrieval_time = sum(retrieval_times) / len(retrieval_times)
        assert avg_retrieval_time < 0.1, f"Average retrieval time {avg_retrieval_time:.3f}s is too high"
        
        print(f"Average retrieval time: {avg_retrieval_time:.3f}s")
    
    def test_safety_critic_performance(self, performance_test_setup):
        """Test safety critic performance."""
        critic = performance_test_setup["critic"]
        
        # Test various response types
        test_responses = [
            # Valid response
            {
                'checklist': [
                    {
                        'title': 'Cool Burn',
                        'action': 'Cool burn with running water for 10-20 minutes',
                        'source': {'doc_id': 'ifrc_burns', 'loc': [0, 50]}
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice'}
            },
            # Response with emergency keywords
            {
                'checklist': [
                    {
                        'title': 'Check Unconscious Person',
                        'action': 'Check if person is unconscious and call 911',
                        'source': {'doc_id': 'ifrc_cpr', 'loc': [0, 50]}
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice'}
            },
            # Response that should be blocked
            {
                'checklist': [
                    {
                        'title': 'Medical Diagnosis',
                        'action': 'I diagnose this condition and prescribe medication',
                        # Missing source
                    }
                ],
                'meta': {}  # Missing disclaimer
            }
        ]
        
        review_times = []
        
        for response in test_responses:
            start_time = time.time()
            decision = critic.review_response(response)
            end_time = time.time()
            
            review_time = end_time - start_time
            review_times.append(review_time)
            
            # Verify decision is made
            assert hasattr(decision, 'status')
            assert hasattr(decision, 'reasons')
            
            # Each review should be fast
            assert review_time < 1.0, f"Safety review time {review_time:.3f}s too slow"
        
        avg_review_time = sum(review_times) / len(review_times)
        assert avg_review_time < 0.5, f"Average safety review time {avg_review_time:.3f}s is too high"
        
        print(f"Average safety review time: {avg_review_time:.3f}s")
    
    def test_memory_usage(self, performance_test_client):
        """Test memory usage during operation."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")
            
        import gc
        
        client = performance_test_client["client"]
        process = psutil.Process()
        
        # Measure initial memory
        gc.collect()
        initial_memory = process.memory_info().rss
        
        # Perform multiple operations
        for i in range(20):
            response = client.post("/chat", json={
                "query": f"Emergency query {i}",
                "conversation_id": f"memory-test-{i}"
            })
            assert response.status_code == 200
        
        # Force garbage collection
        gc.collect()
        
        # Measure final memory
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        memory_increase_mb = memory_increase / (1024 * 1024)
        assert memory_increase_mb < 100, f"Memory usage increased by {memory_increase_mb:.2f}MB"
        
        print(f"Memory usage increase: {memory_increase_mb:.2f}MB")
    
    def test_concurrent_requests_performance(self, performance_test_client):
        """Test performance under concurrent load."""
        client = performance_test_client["client"]
        
        results = []
        errors = []
        
        def make_request(thread_id):
            try:
                start_time = time.time()
                response = client.post("/chat", json={
                    "query": f"Emergency query from thread {thread_id}",
                    "conversation_id": f"concurrent-{thread_id}"
                })
                end_time = time.time()
                
                response_time = end_time - start_time
                results.append((thread_id, response_time, response.status_code))
                
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start concurrent requests
        threads = []
        num_threads = 10
        
        start_time = time.time()
        
        for i in range(num_threads):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == num_threads
        
        # All requests should be successful
        for thread_id, response_time, status_code in results:
            assert status_code == 200
            assert response_time < 10.0  # Individual request time limit
        
        # Total time should be reasonable for concurrent execution
        assert total_time < 15.0, f"Total concurrent execution time {total_time:.2f}s too high"
        
        avg_response_time = sum(r[1] for r in results) / len(results)
        print(f"Concurrent requests - Total time: {total_time:.2f}s, Avg response: {avg_response_time:.2f}s")
    
    def test_large_corpus_performance(self, performance_test_setup):
        """Test performance with larger corpus content."""
        db = performance_test_setup["db"]
        browser_tool = performance_test_setup["browser_tool"]
        
        # Add more content to simulate larger corpus
        for doc_num in range(5, 15):  # Add 10 more documents
            doc_id = f"large_doc_{doc_num}"
            db.add_document(doc_id, f"Large Document {doc_num}", f"/test/{doc_id}.pdf")
            
            # Add many chunks per document
            for chunk_num in range(50):  # 50 chunks per document
                start_offset = chunk_num * 200
                end_offset = (chunk_num + 1) * 200 - 1
                content = f"Large corpus content for document {doc_num} chunk {chunk_num}. " * 10
                db.add_chunk(doc_id, content, start_offset, end_offset, chunk_num // 10 + 1)
        
        # Test search performance with larger corpus
        start_time = time.time()
        results = browser_tool.search("emergency response content")
        search_time = time.time() - start_time
        
        assert len(results) > 0
        assert search_time < 2.0, f"Search time {search_time:.3f}s too slow for large corpus"
        
        # Test multiple searches
        search_times = []
        for query in ["emergency", "response", "content", "document", "chunk"]:
            start_time = time.time()
            browser_tool.search(query)
            search_time = time.time() - start_time
            search_times.append(search_time)
        
        avg_search_time = sum(search_times) / len(search_times)
        assert avg_search_time < 1.0, f"Average search time {avg_search_time:.3f}s too slow for large corpus"
        
        print(f"Large corpus search performance - Average: {avg_search_time:.3f}s")
    
    @pytest.mark.slow
    def test_extended_operation_performance(self, performance_test_client):
        """Test performance during extended operation."""
        client = performance_test_client["client"]
        
        start_time = time.time()
        operation_count = 0
        response_times = []
        
        # Run for 30 seconds
        while time.time() - start_time < 30:
            request_start = time.time()
            
            response = client.post("/chat", json={
                "query": f"Extended operation query {operation_count}",
                "conversation_id": f"extended-{operation_count}"
            })
            
            request_end = time.time()
            response_time = request_end - request_start
            response_times.append(response_time)
            
            assert response.status_code == 200
            operation_count += 1
            
            # Small delay between requests
            time.sleep(0.1)
        
        total_time = time.time() - start_time
        
        # Should have completed many operations
        assert operation_count > 50, f"Only completed {operation_count} operations in {total_time:.1f}s"
        
        # Performance should remain consistent
        avg_response_time = sum(response_times) / len(response_times)
        assert avg_response_time < 5.0, f"Average response time {avg_response_time:.2f}s degraded during extended operation"
        
        # Check for performance degradation over time
        first_half = response_times[:len(response_times)//2]
        second_half = response_times[len(response_times)//2:]
        
        first_half_avg = sum(first_half) / len(first_half)
        second_half_avg = sum(second_half) / len(second_half)
        
        # Second half shouldn't be significantly slower
        degradation_ratio = second_half_avg / first_half_avg
        assert degradation_ratio < 2.0, f"Performance degraded by {degradation_ratio:.2f}x during extended operation"
        
        print(f"Extended operation: {operation_count} ops in {total_time:.1f}s, avg response: {avg_response_time:.2f}s")
    
    def test_resource_cleanup_performance(self, performance_test_client):
        """Test that resources are properly cleaned up."""
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")
            
        import gc
        
        client = performance_test_client["client"]
        process = psutil.Process()
        
        # Measure initial state
        initial_memory = process.memory_info().rss
        initial_threads = threading.active_count()
        
        # Perform operations that might create resources
        for i in range(50):
            response = client.post("/chat", json={
                "query": f"Resource test query {i}",
                "conversation_id": f"resource-test-{i}"
            })
            assert response.status_code == 200
        
        # Force cleanup
        gc.collect()
        time.sleep(1)  # Allow time for cleanup
        
        # Measure final state
        final_memory = process.memory_info().rss
        final_threads = threading.active_count()
        
        # Memory should not have grown excessively
        memory_increase = (final_memory - initial_memory) / (1024 * 1024)
        assert memory_increase < 50, f"Memory increased by {memory_increase:.2f}MB - possible leak"
        
        # Thread count should be stable
        thread_increase = final_threads - initial_threads
        assert thread_increase <= 2, f"Thread count increased by {thread_increase} - possible leak"
        
        print(f"Resource cleanup - Memory: +{memory_increase:.2f}MB, Threads: +{thread_increase}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])