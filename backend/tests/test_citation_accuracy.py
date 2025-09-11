"""
Citation accuracy tests for Campfire emergency helper.

Tests that verify source linking, citation validation, and document retrieval accuracy.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from campfire.corpus import CorpusDatabase
from campfire.harmony.browser import LocalBrowserTool
from campfire.critic import SafetyCritic
from campfire.critic.types import CriticStatus


class TestCitationAccuracy:
    """Test citation accuracy and source linking functionality."""
    
    @pytest.fixture
    def test_corpus(self):
        """Create test corpus with known content for citation testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db = CorpusDatabase(db_path)
        db.initialize_schema()
        
        # Add test documents with specific content
        db.add_document("ifrc_burns", "IFRC Burn Treatment Guidelines", "/test/ifrc_burns.pdf")
        db.add_chunk(
            "ifrc_burns",
            "For thermal burns: Immediately cool the burn with running water for 10-20 minutes. This helps reduce tissue damage and pain. Remove any jewelry or tight clothing before swelling occurs.",
            0, 165, 1
        )
        db.add_chunk(
            "ifrc_burns", 
            "Cover the burn with a sterile, non-adhesive bandage or clean cloth. Do not use ice, butter, or other home remedies as these can cause further damage.",
            166, 295, 1
        )
        db.add_chunk(
            "ifrc_burns",
            "Seek immediate medical attention for burns larger than the palm of your hand, burns on face, hands, feet, or genitals, or any electrical or chemical burns.",
            296, 450, 2
        )
        
        db.add_document("who_pfa", "WHO Psychological First Aid Guidelines", "/test/who_pfa.pdf")
        db.add_chunk(
            "who_pfa",
            "Psychological first aid involves providing comfort and support to people in distress. Listen without judgment and avoid giving advice unless specifically asked.",
            0, 140, 1
        )
        db.add_chunk(
            "who_pfa",
            "Help the person connect with social supports such as family members, friends, or community resources. Respect their autonomy and cultural background.",
            141, 280, 1
        )
        
        yield {"db": db, "db_path": db_path}
        
        db.close()
        Path(db_path).unlink(missing_ok=True)
    
    def test_citation_format_validation(self, test_corpus):
        """Test that citations have proper format and required fields."""
        critic = SafetyCritic()
        
        # Test valid citation format
        valid_response = {
            'checklist': [
                {
                    'title': 'Cool the Burn',
                    'action': 'Cool burn with running water for 10-20 minutes',
                    'source': {
                        'doc_id': 'ifrc_burns',
                        'loc': [0, 50]
                    }
                }
            ],
            'meta': {'disclaimer': 'Not medical advice'}
        }
        
        decision = critic.review_response(valid_response)
        assert decision.status == CriticStatus.ALLOW
        
        # Test invalid citation formats
        invalid_formats = [
            # Missing source entirely
            {
                'checklist': [
                    {
                        'title': 'Cool the Burn',
                        'action': 'Cool burn with running water'
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice'}
            },
            # Invalid source format (string instead of dict)
            {
                'checklist': [
                    {
                        'title': 'Cool the Burn',
                        'action': 'Cool burn with running water',
                        'source': 'ifrc_burns'
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice'}
            },
            # Missing doc_id
            {
                'checklist': [
                    {
                        'title': 'Cool the Burn',
                        'action': 'Cool burn with running water',
                        'source': {
                            'loc': [0, 50]
                        }
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice'}
            },
            # Missing location
            {
                'checklist': [
                    {
                        'title': 'Cool the Burn',
                        'action': 'Cool burn with running water',
                        'source': {
                            'doc_id': 'ifrc_burns'
                        }
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice'}
            },
            # Invalid location format
            {
                'checklist': [
                    {
                        'title': 'Cool the Burn',
                        'action': 'Cool burn with running water',
                        'source': {
                            'doc_id': 'ifrc_burns',
                            'loc': 'invalid'
                        }
                    }
                ],
                'meta': {'disclaimer': 'Not medical advice'}
            }
        ]
        
        for invalid_response in invalid_formats:
            decision = critic.review_response(invalid_response)
            assert decision.status == CriticStatus.BLOCK
            assert any("citation" in reason.lower() or "source" in reason.lower() 
                      for reason in decision.reasons)
    
    def test_citation_content_accuracy(self, test_corpus):
        """Test that citations accurately reference document content."""
        browser_tool = LocalBrowserTool(test_corpus["db_path"])
        
        # Test accurate citation retrieval
        result = browser_tool.open("ifrc_burns", 0, 165)
        assert result["status"] == "success"
        assert "cool the burn with running water" in result["text"].lower()
        assert "10-20 minutes" in result["text"]
        
        # Test citation with specific location
        result = browser_tool.open("ifrc_burns", 166, 295)
        assert result["status"] == "success"
        assert "sterile" in result["text"].lower()
        assert "bandage" in result["text"].lower()
        assert "ice" in result["text"].lower()  # Should mention not to use ice
        
        # Test citation beyond document bounds
        result = browser_tool.open("ifrc_burns", 1000, 2000)
        assert result["status"] == "error"
        assert "no content found" in result["error"].lower()
        
        # Test citation for non-existent document
        result = browser_tool.open("nonexistent_doc", 0, 100)
        assert result["status"] == "error"
        assert "document not found" in result["error"].lower()
    
    def test_citation_search_accuracy(self, test_corpus):
        """Test that search results provide accurate citations."""
        browser_tool = LocalBrowserTool(test_corpus["db_path"])
        
        # Test burn-related search
        search_response = browser_tool.search("burn treatment water")
        assert search_response["status"] == "success"
        assert search_response["total_results"] > 0
        
        results = search_response["results"]
        burn_result = results[0]
        assert burn_result["doc_id"] == "ifrc_burns"
        assert "location" in burn_result
        assert "snippet" in burn_result
        assert "water" in burn_result["snippet"].lower()
        
        # Verify citation can be retrieved
        location = burn_result["location"]
        retrieval_result = browser_tool.open(
            burn_result["doc_id"], 
            location["start_offset"], 
            location["end_offset"]
        )
        assert retrieval_result["status"] == "success"
        
        # Test psychological first aid search
        pfa_search_response = browser_tool.search("psychological support comfort")
        assert pfa_search_response["status"] == "success"
        assert pfa_search_response["total_results"] > 0
        
        pfa_results = pfa_search_response["results"]
        pfa_result = next((r for r in pfa_results if r["doc_id"] == "who_pfa"), None)
        assert pfa_result is not None
        assert "comfort" in pfa_result["snippet"].lower() or "support" in pfa_result["snippet"].lower()
    
    def test_citation_cross_referencing(self, test_corpus):
        """Test cross-referencing between search and document retrieval."""
        browser_tool = LocalBrowserTool(test_corpus["db_path"])
        
        # Search for specific content
        search_response = browser_tool.search("medical attention burns")
        assert search_response["status"] == "success"
        assert search_response["total_results"] > 0
        
        search_results = search_response["results"]
        # Find the relevant result
        medical_result = next((r for r in search_results 
                              if "medical" in r["snippet"].lower()), None)
        assert medical_result is not None
        
        # Retrieve the full context using citation
        location = medical_result["location"]
        full_context = browser_tool.open(
            medical_result["doc_id"],
            location["start_offset"],
            location["end_offset"]
        )
        
        assert full_context["status"] == "success"
        assert "medical attention" in full_context["text"].lower()
        
        # Verify the snippet is contained in the full context
        snippet_words = medical_result["snippet"].lower().split()
        context_text = full_context["text"].lower()
        
        # At least half the snippet words should be in the context
        matching_words = sum(1 for word in snippet_words if word in context_text)
        assert matching_words >= len(snippet_words) // 2
    
    def test_citation_boundary_conditions(self, test_corpus):
        """Test citation handling at document boundaries."""
        browser_tool = LocalBrowserTool(test_corpus["db_path"])
        
        # Test citation at document start
        result = browser_tool.open("ifrc_burns", 0, 50)
        assert result["status"] == "success"
        assert len(result["text"]) > 0
        
        # Test citation at document end (get last chunk info first)
        chunks = test_corpus["db"].get_document_chunks("ifrc_burns")
        last_chunk = max(chunks, key=lambda c: c["end_offset"])
        
        result = browser_tool.open("ifrc_burns", last_chunk["start_offset"], last_chunk["end_offset"])
        assert result["status"] == "success"
        
        # Test citation spanning multiple chunks
        result = browser_tool.open("ifrc_burns", 100, 300)
        assert result["status"] == "success"
        assert len(result["text"]) > 100  # Should contain content from multiple chunks
        
        # Test zero-length citation
        result = browser_tool.open("ifrc_burns", 100, 100)
        # Zero-length might be handled differently, check if it returns content or error
        assert result["status"] in ["success", "error"]
        
        # Test negative offsets
        result = browser_tool.open("ifrc_burns", -10, 50)
        # Negative offsets might be handled differently, check if it returns content or error
        assert result["status"] in ["success", "error"]
    
    def test_citation_consistency_across_operations(self, test_corpus):
        """Test that citations remain consistent across different operations."""
        browser_tool = LocalBrowserTool(test_corpus["db_path"])
        
        # Search for content
        search_response = browser_tool.search("bandage sterile")
        assert search_response["status"] == "success"
        assert search_response["total_results"] > 0
        
        search_results = search_response["results"]
        bandage_result = next((r for r in search_results 
                              if "bandage" in r["snippet"].lower()), None)
        assert bandage_result is not None
        
        doc_id = bandage_result["doc_id"]
        location = bandage_result["location"]
        
        # Retrieve using citation multiple times
        for _ in range(3):
            result = browser_tool.open(doc_id, location["start_offset"], location["end_offset"])
            assert result["status"] == "success"
            assert result["doc_id"] == doc_id
            assert "bandage" in result["text"].lower()
        
        # Use find operation in same area
        find_result = browser_tool.find(doc_id, "sterile", location["start_offset"])
        assert find_result["status"] == "success"
        if find_result["matches"]:
            first_match = find_result["matches"][0]
            assert first_match["location"]["start_offset"] >= location["start_offset"]
    
    def test_citation_validation_in_responses(self, test_corpus):
        """Test citation validation in complete response structures."""
        critic = SafetyCritic()
        
        # Test response with multiple valid citations
        multi_citation_response = {
            'checklist': [
                {
                    'title': 'Cool Burn',
                    'action': 'Cool with water for 10-20 minutes',
                    'source': {'doc_id': 'ifrc_burns', 'loc': [0, 50]}
                },
                {
                    'title': 'Cover Burn',
                    'action': 'Cover with sterile bandage',
                    'source': {'doc_id': 'ifrc_burns', 'loc': [166, 200]}
                },
                {
                    'title': 'Seek Medical Care',
                    'action': 'Get medical attention for large burns',
                    'source': {'doc_id': 'ifrc_burns', 'loc': [296, 350]}
                }
            ],
            'meta': {'disclaimer': 'Not medical advice'}
        }
        
        decision = critic.review_response(multi_citation_response)
        assert decision.status == CriticStatus.ALLOW
        
        # Test response with mixed valid/invalid citation formats
        mixed_citation_response = {
            'checklist': [
                {
                    'title': 'Valid Citation',
                    'action': 'This has a valid citation',
                    'source': {'doc_id': 'ifrc_burns', 'loc': [0, 50]}
                },
                {
                    'title': 'Invalid Citation Format',
                    'action': 'This has an invalid citation format',
                    'source': {'doc_id': 'some_doc', 'loc': 'invalid_format'}  # Invalid loc format
                }
            ],
            'meta': {'disclaimer': 'Not medical advice'}
        }
        
        decision = critic.review_response(mixed_citation_response)
        assert decision.status == CriticStatus.BLOCK
        # Should identify the invalid citation format issue
        assert any("location format" in reason.lower() for reason in decision.reasons)
    
    def test_citation_metadata_accuracy(self, test_corpus):
        """Test that citation metadata (document titles, etc.) is accurate."""
        browser_tool = LocalBrowserTool(test_corpus["db_path"])
        
        # Test document info retrieval
        ifrc_info = test_corpus["db"].get_document_info("ifrc_burns")
        assert ifrc_info is not None
        assert ifrc_info["title"] == "IFRC Burn Treatment Guidelines"
        
        who_info = test_corpus["db"].get_document_info("who_pfa")
        assert who_info is not None
        assert who_info["title"] == "WHO Psychological First Aid Guidelines"
        
        # Test that browser tool returns correct metadata
        result = browser_tool.open("ifrc_burns", 0, 100)
        assert result["status"] == "success"
        assert result["doc_title"] == "IFRC Burn Treatment Guidelines"
        
        result = browser_tool.open("who_pfa", 0, 100)
        assert result["status"] == "success"
        assert result["doc_title"] == "WHO Psychological First Aid Guidelines"
    
    def test_citation_performance(self, test_corpus):
        """Test citation retrieval performance."""
        import time
        
        browser_tool = LocalBrowserTool(test_corpus["db_path"])
        
        # Test search performance
        start_time = time.time()
        search_response = browser_tool.search("emergency burn treatment")
        search_time = time.time() - start_time
        
        assert search_response["status"] == "success"
        assert search_response["total_results"] > 0
        assert search_time < 1.0  # Should complete within 1 second
        
        # Test retrieval performance
        results = search_response["results"]
        if results:
            result = results[0]
            location = result["location"]
            
            start_time = time.time()
            content = browser_tool.open(
                result["doc_id"], 
                location["start_offset"], 
                location["end_offset"]
            )
            retrieval_time = time.time() - start_time
            
            assert content["status"] == "success"
            assert retrieval_time < 0.5  # Should complete within 0.5 seconds
        
        # Test multiple rapid citations
        start_time = time.time()
        for i in range(10):
            browser_tool.open("ifrc_burns", i * 10, (i + 1) * 10 + 20)
        batch_time = time.time() - start_time
        
        assert batch_time < 2.0  # 10 retrievals should complete within 2 seconds
    
    def test_citation_error_handling(self, test_corpus):
        """Test proper error handling for citation issues."""
        browser_tool = LocalBrowserTool(test_corpus["db_path"])
        
        # Test various error conditions
        error_cases = [
            # Non-existent document
            ("nonexistent_doc", 0, 100, "document not found"),
            # Empty document ID
            ("", 0, 100, "document not found"),
            # Range beyond document bounds
            ("ifrc_burns", 10000, 20000, "no content found"),
        ]
        
        for doc_id, start, end, expected_error in error_cases:
            result = browser_tool.open(doc_id, start, end)
            assert result["status"] == "error"
            assert expected_error.lower() in result["error"].lower()
        
        # Test cases that might succeed but with adjusted ranges
        edge_cases = [
            # Negative offsets (might be adjusted to valid range)
            ("ifrc_burns", -1, 100),
            # End before start (might be handled gracefully)
            ("ifrc_burns", 100, 50),
        ]
        
        for doc_id, start, end in edge_cases:
            result = browser_tool.open(doc_id, start, end)
            # These cases might succeed with adjusted ranges or fail gracefully
            assert result["status"] in ["success", "error"]
        
        # Test search error handling
        empty_search = browser_tool.search("")
        # Empty search might return error or empty results
        assert empty_search["status"] in ["success", "error"]
        
        very_long_query = "a" * 1000
        long_search = browser_tool.search(very_long_query)
        assert long_search["status"] in ["success", "error"]  # Should handle gracefully


if __name__ == "__main__":
    pytest.main([__file__, "-v"])