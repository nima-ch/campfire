"""Tests for local browser tool implementation."""

import pytest
import tempfile
import os
from pathlib import Path

from campfire.harmony.browser import LocalBrowserTool
from campfire.corpus.database import CorpusDatabase


class TestLocalBrowserTool:
    """Test cases for LocalBrowserTool."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Initialize database with test data
        db = CorpusDatabase(db_path)
        db.initialize_schema()
        
        # Add test documents
        db.add_document("doc1", "First Aid Guidelines", "/path/to/doc1.pdf")
        db.add_document("doc2", "Emergency Procedures", "/path/to/doc2.pdf")
        
        # Add test chunks
        db.add_chunk("doc1", "First aid for burns: Cool the burn with cold water for at least 10 minutes.", 0, 75, 1)
        db.add_chunk("doc1", "Remove any jewelry or tight clothing before swelling begins.", 76, 140, 1)
        db.add_chunk("doc1", "Cover the burn with a sterile gauze bandage.", 141, 185, 2)
        db.add_chunk("doc2", "In case of gas leak: Turn off the gas supply immediately.", 0, 58, 1)
        db.add_chunk("doc2", "Evacuate the area and call emergency services.", 59, 103, 1)
        db.add_chunk("doc2", "Do not use electrical switches or create sparks.", 104, 150, 2)
        
        yield db_path
        
        # Cleanup
        db.close()
        os.unlink(db_path)
    
    @pytest.fixture
    def browser_tool(self, temp_db):
        """Create browser tool instance with test database."""
        return LocalBrowserTool(temp_db)
    
    def test_search_basic(self, browser_tool):
        """Test basic search functionality."""
        result = browser_tool.search("burn")
        
        assert result["status"] == "success"
        assert result["query"] == "burn"
        assert result["total_results"] > 0
        
        # Should find burn-related content
        found_burn = any("burn" in r["snippet"].lower() for r in result["results"])
        assert found_burn
    
    def test_search_with_limit(self, browser_tool):
        """Test search with result limit."""
        result = browser_tool.search("emergency", k=1)
        
        assert result["status"] == "success"
        assert len(result["results"]) <= 1
    
    def test_search_no_results(self, browser_tool):
        """Test search with no matching results."""
        result = browser_tool.search("nonexistent_term_xyz")
        
        assert result["status"] == "success"
        assert result["total_results"] == 0
        assert result["results"] == []
    
    def test_search_result_format(self, browser_tool):
        """Test search result format and content."""
        result = browser_tool.search("water")
        
        assert result["status"] == "success"
        assert len(result["results"]) > 0
        
        first_result = result["results"][0]
        assert "doc_id" in first_result
        assert "doc_title" in first_result
        assert "snippet" in first_result
        assert "location" in first_result
        
        location = first_result["location"]
        assert "start_offset" in location
        assert "end_offset" in location
        assert "page_number" in location
    
    def test_open_valid_range(self, browser_tool):
        """Test opening a valid text range."""
        result = browser_tool.open("doc1", 0, 75)
        
        assert result["status"] == "success"
        assert result["doc_id"] == "doc1"
        assert result["doc_title"] == "First Aid Guidelines"
        assert "burn" in result["text"].lower()
        assert "water" in result["text"].lower()
    
    def test_open_invalid_doc(self, browser_tool):
        """Test opening non-existent document."""
        result = browser_tool.open("nonexistent_doc", 0, 100)
        
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()
        assert result["text"] == ""
    
    def test_open_invalid_range(self, browser_tool):
        """Test opening invalid range in valid document."""
        result = browser_tool.open("doc1", 1000, 2000)
        
        assert result["status"] == "error"
        assert "no content found" in result["error"].lower()
        assert result["text"] == ""
    
    def test_open_overlapping_chunks(self, browser_tool):
        """Test opening range that spans multiple chunks."""
        result = browser_tool.open("doc1", 50, 150)
        
        assert result["status"] == "success"
        assert result["doc_id"] == "doc1"
        # Should contain text from multiple chunks
        assert len(result["text"]) > 50
    
    def test_find_pattern_exists(self, browser_tool):
        """Test finding existing pattern in document."""
        result = browser_tool.find("doc1", "burn", 0)
        
        assert result["status"] == "success"
        assert result["doc_id"] == "doc1"
        assert result["pattern"] == "burn"
        assert result["total_matches"] > 0
        
        first_match = result["matches"][0]
        assert "text" in first_match
        assert "context" in first_match
        assert "location" in first_match
        assert first_match["text"].lower() == "burn"
    
    def test_find_pattern_not_exists(self, browser_tool):
        """Test finding non-existent pattern."""
        result = browser_tool.find("doc1", "nonexistent_pattern", 0)
        
        assert result["status"] == "success"
        assert result["total_matches"] == 0
        assert result["matches"] == []
    
    def test_find_with_after_position(self, browser_tool):
        """Test finding pattern after specific position."""
        # First find all occurrences
        all_result = browser_tool.find("doc1", "the", 0)
        
        # Then find only after position 100
        after_result = browser_tool.find("doc1", "the", 100)
        
        assert after_result["status"] == "success"
        assert after_result["search_after"] == 100
        
        # Should have fewer or equal matches
        assert len(after_result["matches"]) <= len(all_result["matches"])
        
        # All matches should be after position 100
        for match in after_result["matches"]:
            assert match["location"]["start_offset"] >= 100
    
    def test_find_invalid_doc(self, browser_tool):
        """Test finding pattern in non-existent document."""
        result = browser_tool.find("nonexistent_doc", "pattern", 0)
        
        assert result["status"] == "success"
        assert result["total_matches"] == 0
        assert result["matches"] == []
    
    def test_find_case_insensitive(self, browser_tool):
        """Test that find is case insensitive."""
        lower_result = browser_tool.find("doc1", "burn", 0)
        upper_result = browser_tool.find("doc1", "BURN", 0)
        mixed_result = browser_tool.find("doc1", "Burn", 0)
        
        # All should find the same matches
        assert lower_result["total_matches"] == upper_result["total_matches"]
        assert lower_result["total_matches"] == mixed_result["total_matches"]
    
    def test_snippet_creation(self, browser_tool):
        """Test snippet creation with query highlighting."""
        # Test the internal method
        text = "This is a long text about first aid procedures for burns and other injuries."
        snippet = browser_tool._create_snippet(text, "burns", max_length=30)
        
        assert len(snippet) <= 35  # Account for ellipsis
        assert "burns" in snippet.lower()
    
    def test_combine_chunks(self, browser_tool):
        """Test chunk combination functionality."""
        # Create test chunks
        chunks = [
            {
                "text": "First chunk of text.",
                "start_offset": 0,
                "end_offset": 20
            },
            {
                "text": "Second chunk continues here.",
                "start_offset": 21,
                "end_offset": 49
            }
        ]
        
        combined = browser_tool._combine_chunks(chunks, 0, 49)
        assert "First chunk" in combined
        assert "Second chunk" in combined
    
    def test_combine_chunks_with_gaps(self, browser_tool):
        """Test chunk combination with gaps."""
        chunks = [
            {
                "text": "First chunk.",
                "start_offset": 0,
                "end_offset": 12
            },
            {
                "text": "Third chunk after gap.",
                "start_offset": 50,
                "end_offset": 72
            }
        ]
        
        combined = browser_tool._combine_chunks(chunks, 0, 72)
        assert "[...]" in combined  # Gap indicator
    
    def test_find_pattern_in_chunk(self, browser_tool):
        """Test pattern finding within a single chunk."""
        chunk = {
            "text": "This text contains multiple burn references and burn treatments.",
            "start_offset": 100,
            "end_offset": 164,
            "page_number": 1
        }
        
        matches = browser_tool._find_pattern_in_chunk(chunk, "burn", 100)
        
        assert len(matches) == 2  # Two occurrences of "burn"
        
        for match in matches:
            assert match["text"] == "burn"
            assert match["location"]["start_offset"] >= 100
            assert "burn" in match["context"].lower()
    
    def test_search_error_handling(self, browser_tool):
        """Test search error handling."""
        # Simulate error by using invalid database path
        browser_tool.db.db_path = Path("/invalid/path/to/database.db")
        browser_tool.db._conn = None  # Force reconnection attempt
        
        result = browser_tool.search("test")
        assert result["status"] == "error"
        assert "error" in result
        assert result["results"] == []
    
    def test_open_error_handling(self, browser_tool):
        """Test open error handling."""
        # Simulate error by using invalid database path
        browser_tool.db.db_path = Path("/invalid/path/to/database.db")
        browser_tool.db._conn = None  # Force reconnection attempt
        
        result = browser_tool.open("doc1", 0, 100)
        assert result["status"] == "error"
        assert "error" in result
        assert result["text"] == ""
    
    def test_find_error_handling(self, browser_tool):
        """Test find error handling."""
        # Simulate error by using invalid database path
        browser_tool.db.db_path = Path("/invalid/path/to/database.db")
        browser_tool.db._conn = None  # Force reconnection attempt
        
        result = browser_tool.find("doc1", "pattern", 0)
        assert result["status"] == "error"
        assert "error" in result
        assert result["matches"] == []
    
    def test_close_connection(self, browser_tool):
        """Test closing database connection."""
        # Should not raise exception
        browser_tool.close()
        
        # Database should reconnect automatically, so this should work
        result = browser_tool.search("burn")
        assert result["status"] == "success"


class TestBrowserToolIntegration:
    """Integration tests for browser tool with real-like data."""
    
    @pytest.fixture
    def integration_db(self):
        """Create database with more realistic test data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db = CorpusDatabase(db_path)
        db.initialize_schema()
        
        # Add realistic emergency guidance content
        db.add_document("ifrc_2020", "IFRC First Aid Guidelines 2020", "/corpus/ifrc_2020.pdf")
        
        # Add realistic chunks with overlapping content
        chunks = [
            ("Burns are injuries to tissues caused by heat, chemicals, electricity, or radiation. "
             "The severity depends on the temperature, duration of contact, and area affected.", 0, 150, 15),
            ("For minor burns: Cool the burn with cold running water for at least 10 minutes. "
             "Remove jewelry and tight clothing before swelling occurs.", 151, 280, 15),
            ("Cover the burn with a sterile, non-adhesive bandage or clean cloth. "
             "Do not apply ice, butter, or other home remedies.", 281, 400, 16),
            ("Seek immediate medical attention for burns that are larger than the palm of your hand, "
             "involve the face, hands, feet, or genitals, or show signs of infection.", 401, 550, 16),
        ]
        
        for text, start, end, page in chunks:
            db.add_chunk("ifrc_2020", text, start, end, page)
        
        yield db_path
        
        db.close()
        os.unlink(db_path)
    
    def test_realistic_search_workflow(self, integration_db):
        """Test realistic search workflow."""
        browser = LocalBrowserTool(integration_db)
        
        # Search for burn treatment
        search_result = browser.search("burn")
        
        assert search_result["status"] == "success"
        assert search_result["total_results"] > 0
        
        # Get first result and open the full context
        first_result = search_result["results"][0]
        doc_id = first_result["doc_id"]
        location = first_result["location"]
        
        open_result = browser.open(
            doc_id, 
            location["start_offset"], 
            location["end_offset"]
        )
        
        assert open_result["status"] == "success"
        assert "burn" in open_result["text"].lower()  # Should contain burn-related content
        
        # Find specific guidance within the opened text
        find_result = browser.find(doc_id, "burn", location["start_offset"])
        
        assert find_result["status"] == "success"
        if find_result["total_matches"] > 0:
            assert "burn" in find_result["matches"][0]["text"].lower()
        
        browser.close()
    
    def test_multi_step_information_gathering(self, integration_db):
        """Test multi-step information gathering workflow."""
        browser = LocalBrowserTool(integration_db)
        
        # Step 1: Search for general burn information
        search_result = browser.search("burns severity")
        assert search_result["status"] == "success"
        
        if search_result["total_results"] > 0:
            # Step 2: Open the most relevant result
            first_result = search_result["results"][0]
            open_result = browser.open(
                first_result["doc_id"],
                first_result["location"]["start_offset"],
                first_result["location"]["end_offset"]
            )
            assert open_result["status"] == "success"
            
            # Step 3: Find specific treatment details
            find_result = browser.find(
                first_result["doc_id"],
                "medical attention",
                first_result["location"]["start_offset"]
            )
            assert find_result["status"] == "success"
        
        browser.close()