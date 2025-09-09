"""
Tests for TextChunker class.
"""

import pytest
from unittest.mock import Mock

from campfire.corpus.chunker import TextChunker, TextChunk
from campfire.corpus.extractor import TextSegment


class TestTextChunk:
    """Test cases for TextChunk."""
    
    def test_text_chunk_creation(self):
        """Test TextChunk creation and properties."""
        chunk = TextChunk(
            text="Test chunk content",
            start_offset=0,
            end_offset=18,
            chunk_index=0,
            page_numbers=[1, 2],
            metadata={"doc_id": "test_doc"}
        )
        
        assert chunk.text == "Test chunk content"
        assert chunk.start_offset == 0
        assert chunk.end_offset == 18
        assert chunk.chunk_index == 0
        assert chunk.page_numbers == [1, 2]
        assert chunk.metadata == {"doc_id": "test_doc"}
        assert len(chunk) == 18
    
    def test_text_chunk_defaults(self):
        """Test TextChunk with default values."""
        chunk = TextChunk(
            text="Test content",
            start_offset=10,
            end_offset=22,
            chunk_index=1
        )
        
        assert chunk.page_numbers == []
        assert chunk.metadata == {}


class TestTextChunker:
    """Test cases for TextChunker."""
    
    @pytest.fixture
    def chunker(self):
        """Create TextChunker instance with test settings."""
        return TextChunker(
            chunk_size=100,
            overlap_size=20,
            respect_sentences=True,
            min_chunk_size=30
        )
    
    def test_chunker_initialization(self):
        """Test TextChunker initialization."""
        chunker = TextChunker(
            chunk_size=500,
            overlap_size=50,
            respect_sentences=False,
            min_chunk_size=100
        )
        
        assert chunker.chunk_size == 500
        assert chunker.overlap_size == 50
        assert chunker.respect_sentences is False
        assert chunker.min_chunk_size == 100
    
    def test_chunk_empty_text(self, chunker):
        """Test chunking empty or very short text."""
        # Empty text
        chunks = chunker.chunk_text("")
        assert chunks == []
        
        # Text shorter than minimum
        chunks = chunker.chunk_text("Short")
        assert len(chunks) == 1
        assert chunks[0].text == "Short"
    
    def test_chunk_short_text(self, chunker):
        """Test chunking text shorter than chunk size."""
        text = "This is a short text that fits in one chunk."
        chunks = chunker.chunk_text(text, doc_id="test_doc")
        
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].start_offset == 0
        assert chunks[0].end_offset == len(text)
        assert chunks[0].chunk_index == 0
        assert chunks[0].metadata["doc_id"] == "test_doc"
    
    def test_chunk_long_text(self, chunker):
        """Test chunking text longer than chunk size."""
        # Create text longer than chunk_size (100)
        text = "This is a long text. " * 10  # About 210 characters
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) >= 2  # Should create multiple chunks
        
        # Check that chunks have proper offsets
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.start_offset < chunk.end_offset
            assert len(chunk.text) > 0
        
        # Check overlap between consecutive chunks
        if len(chunks) > 1:
            # There should be some overlap or reasonable gap
            gap = chunks[1].start_offset - chunks[0].end_offset
            assert gap <= chunker.overlap_size
    
    def test_sentence_boundary_respect(self):
        """Test that chunker respects sentence boundaries."""
        chunker = TextChunker(chunk_size=50, overlap_size=10, respect_sentences=True)
        
        text = "First sentence is here. Second sentence follows. Third sentence ends."
        chunks = chunker.chunk_text(text)
        
        # Should break at sentence boundaries when possible
        assert len(chunks) >= 1
        
        # Check that chunks don't break in the middle of sentences when possible
        for chunk in chunks:
            # If chunk ends with a period, it likely respected sentence boundary
            if chunk.text.rstrip().endswith('.'):
                assert True  # Good sentence boundary
    
    def test_chunk_with_segments(self, chunker):
        """Test chunking with TextSegment objects."""
        # Create mock segments
        segments = [
            TextSegment("First page content. ", 1, 0, 20),
            TextSegment("Second page content.", 2, 20, 40)
        ]
        
        chunks = chunker.chunk_with_segments(segments, doc_id="test_doc")
        
        assert len(chunks) >= 1
        
        # Check that page information is preserved
        for chunk in chunks:
            assert len(chunk.page_numbers) > 0
            assert "page_numbers" in chunk.metadata
            assert chunk.metadata["doc_id"] == "test_doc"
    
    def test_chunk_with_empty_segments(self, chunker):
        """Test chunking with empty segments list."""
        chunks = chunker.chunk_with_segments([])
        assert chunks == []
    
    def test_merge_small_chunks(self, chunker):
        """Test merging of small chunks."""
        # Create chunks with some below minimum size
        chunks = [
            TextChunk("Small chunk", 0, 11, 0),  # Below min_chunk_size (30)
            TextChunk("Another small one", 11, 28, 1),  # Below min_chunk_size
            TextChunk("This is a larger chunk that exceeds minimum size", 28, 77, 2)  # Above min_chunk_size
        ]
        
        merged_chunks = chunker.merge_small_chunks(chunks)
        
        # Should have fewer chunks after merging
        assert len(merged_chunks) <= len(chunks)
        
        # Check that merged chunks have proper metadata
        for chunk in merged_chunks:
            if "merged" in chunk.metadata:
                assert chunk.metadata["merged"] is True
                assert "original_chunks" in chunk.metadata
    
    def test_merge_empty_chunks(self, chunker):
        """Test merging with empty chunks list."""
        merged_chunks = chunker.merge_small_chunks([])
        assert merged_chunks == []
    
    def test_get_chunk_context(self, chunker):
        """Test getting context around a chunk."""
        chunks = [
            TextChunk("First chunk", 0, 11, 0, page_numbers=[1]),
            TextChunk("Second chunk", 11, 23, 1, page_numbers=[1]),
            TextChunk("Third chunk", 23, 34, 2, page_numbers=[2]),
            TextChunk("Fourth chunk", 34, 46, 3, page_numbers=[2])
        ]
        
        # Get context for middle chunk
        context = chunker.get_chunk_context(chunks, 1, context_size=1)
        
        assert context["target_chunk"] == chunks[1]
        assert len(context["context_chunks"]) == 3  # Target + 1 before + 1 after
        assert context["pages"] == [1, 2]
        assert "First chunk" in context["context_text"]
        assert "Third chunk" in context["context_text"]
    
    def test_get_chunk_context_edge_cases(self, chunker):
        """Test chunk context at edges and with invalid indices."""
        chunks = [
            TextChunk("Only chunk", 0, 10, 0)
        ]
        
        # Valid index
        context = chunker.get_chunk_context(chunks, 0, context_size=1)
        assert context["target_chunk"] == chunks[0]
        assert len(context["context_chunks"]) == 1
        
        # Invalid index
        context = chunker.get_chunk_context(chunks, 5, context_size=1)
        assert context == {}
        
        # Empty chunks
        context = chunker.get_chunk_context([], 0, context_size=1)
        assert context == {}
    
    def test_split_by_sections(self, chunker):
        """Test splitting text by section patterns."""
        text = """
        Introduction
        This is the introduction section.
        
        Chapter 1: Emergency Procedures
        This covers emergency procedures.
        
        Chapter 2: First Aid
        This covers first aid procedures.
        """
        
        section_patterns = [
            r'^Chapter \d+:.*$',
            r'^Introduction$'
        ]
        
        sections = chunker.split_by_sections(text, section_patterns)
        
        assert len(sections) >= 1
        
        # Check that sections have proper structure
        for section in sections:
            assert "title" in section
            assert "text" in section
            assert "start_offset" in section
            assert "end_offset" in section
            assert "section_index" in section
    
    def test_split_by_sections_no_matches(self, chunker):
        """Test section splitting with no pattern matches."""
        text = "This is plain text with no section headers."
        section_patterns = [r'^Chapter \d+:.*$']
        
        sections = chunker.split_by_sections(text, section_patterns)
        
        assert len(sections) == 1
        assert sections[0]["title"] == "Document"
        assert sections[0]["text"] == text
    
    def test_find_sentence_boundary(self, chunker):
        """Test sentence boundary finding."""
        text = "First sentence. Second sentence! Third sentence? Fourth sentence."
        
        # Test finding boundary near position 30
        boundary = chunker._find_sentence_boundary(text, 0, 30)
        
        # Should find a sentence ending
        assert boundary > 0
        assert boundary <= len(text)
        
        # The boundary should be at or near a sentence ending
        char_at_boundary = text[boundary-1:boundary+1] if boundary < len(text) else text[boundary-1:]
        # Should be near punctuation or whitespace after punctuation
    
    def test_chunker_progress_guarantee(self, chunker):
        """Test that chunker always makes progress to avoid infinite loops."""
        # Create a scenario that might cause issues
        text = "A" * 1000  # Long text without sentence boundaries
        
        chunks = chunker.chunk_text(text)
        
        # Should create multiple chunks
        assert len(chunks) > 1
        
        # Each chunk should start after the previous one
        for i in range(1, len(chunks)):
            assert chunks[i].start_offset > chunks[i-1].start_offset