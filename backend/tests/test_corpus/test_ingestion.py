"""
Tests for DocumentIngester class.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from campfire.corpus.ingestion import DocumentIngester
from campfire.corpus.database import CorpusDatabase
from campfire.corpus.extractor import PDFExtractor, TextSegment
from campfire.corpus.chunker import TextChunker, TextChunk


class TestDocumentIngester:
    """Test cases for DocumentIngester."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db = CorpusDatabase(db_path)
        db.initialize_schema()
        yield db
        
        db.close()
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def mock_extractor(self):
        """Create mock PDFExtractor."""
        extractor = Mock(spec=PDFExtractor)
        return extractor
    
    @pytest.fixture
    def mock_chunker(self):
        """Create mock TextChunker."""
        chunker = Mock(spec=TextChunker)
        return chunker
    
    @pytest.fixture
    def ingester(self, temp_db, mock_extractor, mock_chunker):
        """Create DocumentIngester with mocked dependencies."""
        return DocumentIngester(temp_db, mock_extractor, mock_chunker)
    
    @pytest.fixture
    def mock_pdf_path(self):
        """Create mock PDF file path."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = Path(f.name)
        yield pdf_path
        pdf_path.unlink(missing_ok=True)
    
    def test_ingester_initialization(self, temp_db):
        """Test DocumentIngester initialization."""
        # With all dependencies provided
        extractor = Mock()
        chunker = Mock()
        ingester = DocumentIngester(temp_db, extractor, chunker)
        
        assert ingester.database is temp_db
        assert ingester.extractor is extractor
        assert ingester.chunker is chunker
        
        # With default dependencies
        ingester = DocumentIngester(temp_db)
        assert ingester.database is temp_db
        assert isinstance(ingester.extractor, PDFExtractor)
        assert isinstance(ingester.chunker, TextChunker)
    
    def test_ingest_pdf_file_not_found(self, ingester):
        """Test ingestion with non-existent PDF file."""
        with pytest.raises(FileNotFoundError):
            ingester.ingest_pdf("nonexistent.pdf")
    
    def test_ingest_pdf_success(self, ingester, mock_pdf_path):
        """Test successful PDF ingestion."""
        # Mock extractor behavior
        mock_segments = [
            TextSegment("Emergency procedures text", 1, 0, 25),
            TextSegment("First aid information", 1, 25, 46)
        ]
        ingester.extractor.extract_text_segments.return_value = mock_segments
        ingester.extractor.get_document_info.return_value = {
            "file_size": 1024,
            "page_count": 1,
            "character_count": 46
        }
        
        # Mock chunker behavior
        mock_chunks = [
            TextChunk("Emergency procedures text", 0, 25, 0, page_numbers=[1]),
            TextChunk("First aid information", 25, 46, 1, page_numbers=[1])
        ]
        ingester.chunker.chunk_with_segments.return_value = mock_chunks
        ingester.chunker.merge_small_chunks.return_value = mock_chunks
        
        # Ingest PDF
        result = ingester.ingest_pdf(mock_pdf_path, doc_id="test_doc", title="Test Document")
        
        # Verify result
        assert result["status"] == "success"
        assert result["doc_id"] == "test_doc"
        assert result["title"] == "Test Document"
        assert result["chunking"]["chunks"] == 2
        
        # Verify database calls
        doc_info = ingester.database.get_document_info("test_doc")
        assert doc_info is not None
        assert doc_info["title"] == "Test Document"
    
    def test_ingest_pdf_already_exists(self, ingester, mock_pdf_path):
        """Test ingestion when document already exists."""
        # Add document to database first
        ingester.database.add_document("test_doc", "Existing Document", str(mock_pdf_path))
        
        # Try to ingest same document
        result = ingester.ingest_pdf(mock_pdf_path, doc_id="test_doc")
        
        assert result["status"] == "skipped"
        assert result["reason"] == "already_exists"
    
    def test_ingest_pdf_no_text_extracted(self, ingester, mock_pdf_path):
        """Test ingestion when no text is extracted."""
        # Mock extractor to return empty segments
        ingester.extractor.extract_text_segments.return_value = []
        
        result = ingester.ingest_pdf(mock_pdf_path, doc_id="test_doc")
        
        assert result["status"] == "failed"
        assert result["reason"] == "no_text_extracted"
    
    def test_ingest_pdf_auto_generated_ids(self, ingester, mock_pdf_path):
        """Test ingestion with auto-generated doc_id and title."""
        # Mock successful extraction
        mock_segments = [TextSegment("Test content", 1, 0, 12)]
        ingester.extractor.extract_text_segments.return_value = mock_segments
        ingester.extractor.get_document_info.return_value = {
            "file_size": 100,
            "page_count": 1,
            "character_count": 12
        }
        
        mock_chunks = [TextChunk("Test content", 0, 12, 0)]
        ingester.chunker.chunk_with_segments.return_value = mock_chunks
        ingester.chunker.merge_small_chunks.return_value = mock_chunks
        
        # Ingest without specifying doc_id or title
        result = ingester.ingest_pdf(mock_pdf_path)
        
        assert result["status"] == "success"
        assert result["doc_id"] is not None
        assert result["title"] == mock_pdf_path.stem
    
    def test_ingest_directory(self, ingester, tmp_path):
        """Test directory ingestion."""
        # Create test PDF files
        pdf1 = tmp_path / "doc1.pdf"
        pdf2 = tmp_path / "doc2.pdf"
        pdf1.touch()
        pdf2.touch()
        
        # Mock successful ingestion for both files
        def mock_ingest_pdf(pdf_path, **kwargs):
            return {
                "doc_id": f"doc_{pdf_path.stem}",
                "status": "success",
                "title": pdf_path.stem
            }
        
        with patch.object(ingester, 'ingest_pdf', side_effect=mock_ingest_pdf):
            results = ingester.ingest_directory(tmp_path)
        
        assert len(results) == 2
        assert all(result["status"] == "success" for result in results)
    
    def test_ingest_directory_not_found(self, ingester):
        """Test directory ingestion with non-existent directory."""
        with pytest.raises(FileNotFoundError):
            ingester.ingest_directory("nonexistent_directory")
    
    def test_ingest_directory_with_failures(self, ingester, tmp_path):
        """Test directory ingestion with some failures."""
        # Create test PDF files
        pdf1 = tmp_path / "doc1.pdf"
        pdf2 = tmp_path / "doc2.pdf"
        pdf1.touch()
        pdf2.touch()
        
        # Mock ingestion with one success and one failure
        def mock_ingest_pdf(pdf_path, **kwargs):
            if "doc1" in str(pdf_path):
                return {"doc_id": "doc1", "status": "success"}
            else:
                raise Exception("Ingestion failed")
        
        with patch.object(ingester, 'ingest_pdf', side_effect=mock_ingest_pdf):
            results = ingester.ingest_directory(tmp_path)
        
        assert len(results) == 2
        # Results order may vary, so check that we have one success and one failure
        statuses = [result["status"] for result in results]
        assert "success" in statuses
        assert "failed" in statuses
    
    def test_reingest_document(self, ingester, mock_pdf_path):
        """Test document re-ingestion."""
        # Add existing document
        ingester.database.add_document("test_doc", "Original Title", str(mock_pdf_path))
        
        # Mock successful ingestion
        def mock_ingest_pdf(pdf_path, doc_id=None, title=None, **kwargs):
            return {
                "doc_id": doc_id,
                "title": title or "Original Title",
                "status": "success"
            }
        
        with patch.object(ingester, 'ingest_pdf', side_effect=mock_ingest_pdf):
            result = ingester.reingest_document("test_doc", mock_pdf_path)
        
        assert result["status"] == "success"
        assert result["doc_id"] == "test_doc"
        assert result["title"] == "Original Title"
    
    def test_validate_ingestion_success(self, ingester):
        """Test validation of successful ingestion."""
        # Add document and chunks
        ingester.database.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        ingester.database.add_chunk("test_doc", "Emergency procedures", 0, 19, 1)
        ingester.database.add_chunk("test_doc", "First aid steps", 20, 35, 1)
        
        validation = ingester.validate_ingestion("test_doc")
        
        assert validation["valid"] is True
        assert validation["doc_id"] == "test_doc"
        assert validation["chunk_count"] == 2
        assert len(validation["issues"]) == 0
        assert validation["search_functional"] is True
    
    def test_validate_ingestion_not_found(self, ingester):
        """Test validation of non-existent document."""
        validation = ingester.validate_ingestion("nonexistent_doc")
        
        assert validation["valid"] is False
        assert "Document not found" in validation["error"]
    
    def test_validate_ingestion_no_chunks(self, ingester):
        """Test validation of document with no chunks."""
        # Add document without chunks
        ingester.database.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        
        validation = ingester.validate_ingestion("test_doc")
        
        assert validation["valid"] is False
        assert "No chunks found" in validation["issues"]
    
    def test_get_ingestion_stats(self, ingester):
        """Test getting ingestion statistics."""
        # Add some test data
        ingester.database.add_document("doc1", "Document 1", "/path/to/doc1.pdf")
        ingester.database.add_document("doc2", "Document 2", "/path/to/doc2.pdf")
        ingester.database.add_chunk("doc1", "Content 1", 0, 9, 1)
        ingester.database.add_chunk("doc2", "Content 2", 0, 9, 1)
        
        stats = ingester.get_ingestion_stats()
        
        assert stats["documents"] == 2
        assert stats["chunks"] == 2
        assert stats["average_chunks_per_doc"] == 1.0
        assert len(stats["documents_list"]) == 2
    
    def test_generate_doc_id(self, ingester):
        """Test document ID generation."""
        pdf_path = Path("/path/to/test_document.pdf")
        
        doc_id = ingester._generate_doc_id(pdf_path)
        
        assert "test_document" in doc_id
        assert len(doc_id) > len("test_document")  # Should include hash
    
    def test_ingest_pdf_extraction_failure(self, ingester, mock_pdf_path):
        """Test ingestion when PDF extraction fails."""
        # Mock extractor to raise exception
        ingester.extractor.extract_text_segments.side_effect = Exception("PDF extraction failed")
        
        with pytest.raises(Exception, match="PDF extraction failed"):
            ingester.ingest_pdf(mock_pdf_path, doc_id="test_doc")
        
        # Verify cleanup - document should not exist
        doc_info = ingester.database.get_document_info("test_doc")
        assert doc_info is None
    
    def test_ingest_pdf_chunking_failure(self, ingester, mock_pdf_path):
        """Test ingestion when chunking fails."""
        # Mock successful extraction but failed chunking
        mock_segments = [TextSegment("Test content", 1, 0, 12)]
        ingester.extractor.extract_text_segments.return_value = mock_segments
        ingester.chunker.chunk_with_segments.side_effect = Exception("Chunking failed")
        
        with pytest.raises(Exception, match="Chunking failed"):
            ingester.ingest_pdf(mock_pdf_path, doc_id="test_doc")
        
        # Verify cleanup
        doc_info = ingester.database.get_document_info("test_doc")
        assert doc_info is None