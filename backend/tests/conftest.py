"""
Pytest configuration and shared fixtures for comprehensive testing.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture(scope="session")
def test_environment():
    """Set up test environment variables."""
    # Set test environment variables
    os.environ["CAMPFIRE_ADMIN_PASSWORD"] = "test-admin-password"
    os.environ["CAMPFIRE_TEST_MODE"] = "true"
    
    yield
    
    # Clean up
    os.environ.pop("CAMPFIRE_ADMIN_PASSWORD", None)
    os.environ.pop("CAMPFIRE_TEST_MODE", None)


@pytest.fixture
def temp_directory():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_network_isolation():
    """Mock network calls to simulate offline mode."""
    with patch('socket.socket') as mock_socket:
        with patch('urllib3.poolmanager.PoolManager') as mock_pool:
            with patch('requests.get') as mock_requests:
                with patch('httpx.get') as mock_httpx:
                    mock_socket.side_effect = OSError("Network unavailable")
                    mock_pool.side_effect = OSError("Network unavailable")
                    mock_requests.side_effect = OSError("Network unavailable")
                    mock_httpx.side_effect = OSError("Network unavailable")
                    yield


@pytest.fixture
def performance_monitor():
    """Monitor performance during tests."""
    import psutil
    import time
    
    process = psutil.Process()
    start_memory = process.memory_info().rss
    start_time = time.time()
    
    yield
    
    end_memory = process.memory_info().rss
    end_time = time.time()
    
    memory_increase = (end_memory - start_memory) / (1024 * 1024)  # MB
    duration = end_time - start_time
    
    # Log performance metrics
    print(f"\nPerformance: {duration:.2f}s, Memory: +{memory_increase:.2f}MB")


# Configure pytest markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "offline: marks tests that require offline simulation"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests that measure performance"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add markers based on test file names
        if "test_offline" in item.nodeid:
            item.add_marker(pytest.mark.offline)
        
        if "test_performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        
        if "test_end_to_end" in item.nodeid or "test_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Mark slow tests
        if any(keyword in item.nodeid for keyword in ["extended", "load", "stress", "large"]):
            item.add_marker(pytest.mark.slow)


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Clean up after each test."""
    yield
    
    # Force garbage collection
    import gc
    gc.collect()


# Test data fixtures
@pytest.fixture
def sample_emergency_scenarios():
    """Sample emergency scenarios for testing."""
    return [
        {
            "query": "Someone is bleeding heavily",
            "expected_keywords": ["pressure", "bleeding", "emergency"],
            "emergency_level": "high"
        },
        {
            "query": "I burned my hand on the stove",
            "expected_keywords": ["cool", "water", "burn"],
            "emergency_level": "medium"
        },
        {
            "query": "Friend is having panic attack",
            "expected_keywords": ["listen", "comfort", "support"],
            "emergency_level": "low"
        },
        {
            "query": "Found someone unconscious",
            "expected_keywords": ["unconscious", "911", "emergency"],
            "emergency_level": "critical"
        }
    ]


@pytest.fixture
def sample_citations():
    """Sample citation data for testing."""
    return [
        {
            "doc_id": "ifrc_burns_2020",
            "title": "IFRC Burn Treatment Guidelines",
            "content": "Cool burn with running water for 10-20 minutes",
            "location": {"start_offset": 0, "end_offset": 50}
        },
        {
            "doc_id": "who_pfa_2011", 
            "title": "WHO Psychological First Aid",
            "content": "Listen without judgment and provide support",
            "location": {"start_offset": 100, "end_offset": 150}
        }
    ]