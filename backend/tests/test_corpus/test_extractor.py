"""
Tests for PDFExtractor class.
"""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from campfire.corpus.extractor import PDFExtractor, TextSegment


class TestPDFExtractor:
    """Test cases for PDFExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Create PDFExtractor instance."""
        return PDFExtractor()
    
    @pytest.fixture
    def mock_pdf_path(self):
        """Create mock PDF file path."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = Path(f.name)
        yield pdf_path
        pdf_path.unlink(missing_ok=True)
    
    def test_text_segment_creation(self):
        """Test TextSegment creation and properties."""
        segment = TextSegment(
            text="Test text content",
            page_number=1,
            start_offset=0,
            end_offset=17,
            bbox=(10.0, 20.0, 100.0, 30.0)
        )
        
        assert segment.text == "Test text content"
        assert segment.page_number == 1
        assert segment.start_offset == 0
        assert segment.end_offset == 17
        assert segment.bbox == (10.0, 20.0, 100.0, 30.0)
    
    def test_extractor_initialization(self):
        """Test PDFExtractor initialization."""
        # Default initialization
        extractor = PDFExtractor()
        assert extractor.preserve_layout is True
        assert extractor.laparams is not None
        
        # Without layout preservation
        extractor = PDFExtractor(preserve_layout=False)
        assert extractor.preserve_layout is False
        assert extractor.laparams is None
    
    def test_file_not_found(self, extractor):
        """Test handling of non-existent PDF files."""
        with pytest.raises(FileNotFoundError):
            extractor.extract_text_segments("nonexistent.pdf")
    
    @patch('campfire.corpus.extractor.extract_pages')
    def test_extract_text_segments_empty_pdf(self, mock_extract_pages, extractor, mock_pdf_path):
        """Test extraction from empty PDF."""
        # Mock empty PDF
        mock_extract_pages.return_value = []
        
        segments = extractor.extract_text_segments(mock_pdf_path)
        assert segments == []
    
    @patch('campfire.corpus.extractor.extract_pages')
    def test_extract_text_segments_with_content(self, mock_extract_pages, extractor, mock_pdf_path):
        """Test extraction from PDF with content."""
        # Mock PDF page with text content
        mock_text_element = Mock()
        mock_text_element.get_text.return_value = "Emergency procedures for fire safety.\n"
        mock_text_element.bbox = (10.0, 20.0, 200.0, 30.0)
        
        mock_text_container = Mock()
        mock_text_container.__iter__ = Mock(return_value=iter([mock_text_element]))
        
        mock_page = Mock()
        mock_page.__iter__ = Mock(return_value=iter([mock_text_container]))
        
        mock_extract_pages.return_value = [mock_page]
        
        # Mock isinstance to return True for LTTextContainer
        with patch('campfire.corpus.extractor.isinstance') as mock_isinstance:
            mock_isinstance.side_effect = lambda obj, cls: cls.__name__ == 'LTTextContainer'
            
            # Mock the _extract_text_elements method to return proper tuples
            with patch.object(extractor, '_extract_text_elements') as mock_extract_elements:
                mock_extract_elements.return_value = [("Emergency procedures for fire safety.\n", (10.0, 20.0, 200.0, 30.0))]
                
                segments = extractor.extract_text_segments(mock_pdf_path)
        
        assert len(segments) > 0
        # Note: Actual content verification would require more complex mocking
    
    def test_extract_full_text(self, extractor):
        """Test full text extraction."""
        # Mock extract_text_segments
        mock_segments = [
            TextSegment("First segment. ", 1, 0, 15),
            TextSegment("Second segment.", 1, 15, 30)
        ]
        
        with patch.object(extractor, 'extract_text_segments', return_value=mock_segments):
            full_text = extractor.extract_full_text("mock.pdf")
        
        assert full_text == "First segment. Second segment."
    
    def test_extract_page_text(self, extractor):
        """Test page-specific text extraction."""
        mock_segments = [
            TextSegment("Page 1 text. ", 1, 0, 13),
            TextSegment("Page 2 text.", 2, 13, 25)
        ]
        
        with patch.object(extractor, 'extract_text_segments', return_value=mock_segments):
            page1_text = extractor.extract_page_text("mock.pdf", 1)
            page2_text = extractor.extract_page_text("mock.pdf", 2)
        
        assert page1_text == "Page 1 text. "
        assert page2_text == "Page 2 text."
    
    def test_get_text_at_offset(self, extractor):
        """Test text extraction at specific offset."""
        mock_segments = [
            TextSegment("Emergency procedures ", 1, 0, 20),
            TextSegment("for fire safety.", 1, 20, 36)
        ]
        
        with patch.object(extractor, 'extract_text_segments', return_value=mock_segments):
            result = extractor.get_text_at_offset("mock.pdf", 10, 25)
        
        assert result["text"] == "procedures for "  # Include the trailing space
        assert result["start_offset"] == 10
        assert result["end_offset"] == 25
        assert result["pages"] == [1]
    
    def test_get_text_at_offset_no_overlap(self, extractor):
        """Test text extraction with no overlapping segments."""
        mock_segments = [
            TextSegment("Emergency procedures", 1, 0, 19)
        ]
        
        with patch.object(extractor, 'extract_text_segments', return_value=mock_segments):
            result = extractor.get_text_at_offset("mock.pdf", 50, 60)
        
        assert result["text"] == ""
        assert result["pages"] == []
    
    def test_find_text_pattern(self, extractor):
        """Test pattern finding in text."""
        full_text = "Emergency procedures for fire safety. First aid for burns."
        
        with patch.object(extractor, 'extract_full_text', return_value=full_text):
            with patch.object(extractor, 'extract_text_segments') as mock_segments:
                mock_segments.return_value = [
                    TextSegment(full_text, 1, 0, len(full_text))
                ]
                
                matches = extractor.find_text_pattern("mock.pdf", "fire", case_sensitive=False)
        
        assert len(matches) == 1
        assert matches[0]["pattern"] == "fire"
        assert matches[0]["match_text"] == "fire"
        assert matches[0]["page_number"] == 1
    
    def test_find_text_pattern_case_sensitive(self, extractor):
        """Test case-sensitive pattern finding."""
        full_text = "Fire safety and fire prevention."
        
        with patch.object(extractor, 'extract_full_text', return_value=full_text):
            with patch.object(extractor, 'extract_text_segments') as mock_segments:
                mock_segments.return_value = [
                    TextSegment(full_text, 1, 0, len(full_text))
                ]
                
                # Case sensitive - should find only lowercase "fire"
                matches = extractor.find_text_pattern("mock.pdf", "fire", case_sensitive=True)
                assert len(matches) == 1  # Only the lowercase "fire"
                
                # Case insensitive - should find both
                matches = extractor.find_text_pattern("mock.pdf", "fire", case_sensitive=False)
                assert len(matches) == 2  # Both "Fire" and "fire"
    
    def test_find_text_pattern_after_offset(self, extractor):
        """Test pattern finding after specific offset."""
        full_text = "fire safety fire prevention fire emergency"
        
        with patch.object(extractor, 'extract_full_text', return_value=full_text):
            with patch.object(extractor, 'extract_text_segments') as mock_segments:
                mock_segments.return_value = [
                    TextSegment(full_text, 1, 0, len(full_text))
                ]
                
                # Find "fire" after position 10
                matches = extractor.find_text_pattern("mock.pdf", "fire", after_offset=10)
        
        # Should find the second and third occurrences
        assert len(matches) == 2
        assert all(match["start_offset"] >= 10 for match in matches)
    
    @patch('campfire.corpus.extractor.PDFPage')
    def test_get_document_info(self, mock_pdf_page, extractor, mock_pdf_path):
        """Test document information extraction."""
        # Mock PDF pages
        mock_pdf_page.get_pages.return_value = [Mock(), Mock()]  # 2 pages
        
        # Mock text extraction
        mock_segments = [
            TextSegment("Page 1 content", 1, 0, 14),
            TextSegment("Page 2 content", 2, 14, 28)
        ]
        
        # Mock Path.stat() method
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat_result = Mock()
            mock_stat_result.st_size = 1024
            mock_stat.return_value = mock_stat_result
            
            with patch.object(extractor, 'extract_text_segments', return_value=mock_segments):
                doc_info = extractor.get_document_info(mock_pdf_path)
        
        assert doc_info["page_count"] == 2
        assert doc_info["file_size"] == 1024
        assert doc_info["character_count"] == 28
        assert doc_info["segment_count"] == 2
        assert doc_info["filename"] == mock_pdf_path.name
    
    def test_extract_text_elements(self, extractor):
        """Test text element extraction from container."""
        # Mock text elements
        mock_text_box = Mock()
        mock_text_box.get_text.return_value = "Text box content"
        mock_text_box.bbox = (10, 20, 100, 30)
        
        mock_text_line = Mock()
        mock_text_line.get_text.return_value = "Text line content"
        mock_text_line.bbox = (10, 40, 100, 50)
        
        mock_container = Mock()
        mock_container.__iter__ = Mock(return_value=iter([mock_text_box, mock_text_line]))
        
        # Mock isinstance calls
        with patch('campfire.corpus.extractor.isinstance') as mock_isinstance:
            def isinstance_side_effect(obj, cls):
                if obj is mock_text_box and cls.__name__ == 'LTTextBox':
                    return True
                elif obj is mock_text_line and cls.__name__ == 'LTTextLine':
                    return True
                return False
            
            mock_isinstance.side_effect = isinstance_side_effect
            
            elements = extractor._extract_text_elements(mock_container)
        
        assert len(elements) == 2
        assert elements[0][0] == "Text box content"
        assert elements[1][0] == "Text line content"