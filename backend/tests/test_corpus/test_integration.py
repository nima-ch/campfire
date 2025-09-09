"""
Integration tests for the complete corpus system.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from campfire.corpus import CorpusDatabase, PDFExtractor, TextChunker, DocumentIngester


class TestCorpusIntegration:
    """Integration tests for the complete corpus system."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def mock_pdf_content(self):
        """Mock PDF content for testing."""
        return """
        Emergency Response Procedures
        
        In case of fire emergency, follow these steps:
        1. Remain calm and assess the situation
        2. Alert others in the area
        3. Call emergency services immediately
        4. Evacuate the building if safe to do so
        
        First Aid Guidelines
        
        For minor burns:
        1. Cool the burn with running water for 10-20 minutes
        2. Remove any jewelry or tight clothing near the burn
        3. Cover with a sterile bandage
        4. Seek medical attention if needed
        """
    
    def test_complete_ingestion_and_search_workflow(self, temp_db_path, mock_pdf_content):
        """Test complete workflow from PDF ingestion to search."""
        # Initialize all components
        db = CorpusDatabase(temp_db_path)
        db.initialize_schema()
        
        extractor = PDFExtractor()
        chunker = TextChunker(chunk_size=200, overlap_size=50)
        ingester = DocumentIngester(db, extractor, chunker)
        
        # Mock PDF extraction to return our test content
        with patch.object(extractor, 'extract_text_segments') as mock_extract:
            with patch.object(extractor, 'get_document_info') as mock_doc_info:
                # Mock segments from the content
                from campfire.corpus.extractor import TextSegment
                segments = [
                    TextSegment(mock_pdf_content, 1, 0, len(mock_pdf_content))
                ]
                mock_extract.return_value = segments
                mock_doc_info.return_value = {
                    "file_size": 1024,
                    "page_count": 1,
                    "character_count": len(mock_pdf_content)
                }
                
                # Create a mock PDF file
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    mock_pdf_path = Path(f.name)
                
                try:
                    # Ingest the document
                    result = ingester.ingest_pdf(
                        mock_pdf_path,
                        doc_id="emergency_guide",
                        title="Emergency Response Guide"
                    )
                    
                    # Verify ingestion was successful
                    assert result["status"] == "success"
                    assert result["doc_id"] == "emergency_guide"
                    assert result["chunking"]["chunks"] > 0
                    
                    # Test search functionality
                    fire_results = db.search("fire emergency")
                    assert len(fire_results) > 0
                    assert any("fire" in result["text"].lower() for result in fire_results)
                    
                    # Test search for first aid
                    aid_results = db.search("first aid")
                    assert len(aid_results) > 0
                    assert any("first aid" in result["text"].lower() for result in aid_results)
                    
                    # Test search for specific procedure
                    burn_results = db.search("burns")
                    assert len(burn_results) > 0
                    assert any("burn" in result["text"].lower() for result in burn_results)
                    
                    # Verify document info
                    doc_info = db.get_document_info("emergency_guide")
                    assert doc_info is not None
                    assert doc_info["title"] == "Emergency Response Guide"
                    
                    # Test chunk retrieval
                    chunks = db.get_document_chunks("emergency_guide")
                    assert len(chunks) > 0
                    
                    # Verify chunks contain expected content
                    all_chunk_text = " ".join(chunk["text"] for chunk in chunks)
                    assert "emergency" in all_chunk_text.lower()
                    assert "first aid" in all_chunk_text.lower()
                    
                finally:
                    mock_pdf_path.unlink(missing_ok=True)
                    db.close()
    
    def test_validation_workflow(self, temp_db_path):
        """Test document validation workflow."""
        # Initialize components
        db = CorpusDatabase(temp_db_path)
        db.initialize_schema()
        
        extractor = PDFExtractor()
        chunker = TextChunker()
        ingester = DocumentIngester(db, extractor, chunker)
        
        # Add a document manually for testing
        db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        db.add_chunk("test_doc", "Emergency response procedures", 0, 28, 1)
        db.add_chunk("test_doc", "First aid guidelines", 29, 48, 1)
        
        # Validate the document
        validation = ingester.validate_ingestion("test_doc")
        
        assert validation["valid"] is True
        assert validation["chunk_count"] == 2
        assert validation["search_functional"] is True
        assert len(validation["issues"]) == 0
        
        db.close()
    
    def test_statistics_and_management(self, temp_db_path):
        """Test corpus statistics and management functions."""
        # Initialize components
        db = CorpusDatabase(temp_db_path)
        db.initialize_schema()
        
        extractor = PDFExtractor()
        chunker = TextChunker()
        ingester = DocumentIngester(db, extractor, chunker)
        
        # Add test documents
        db.add_document("doc1", "Document 1", "/path/to/doc1.pdf")
        db.add_document("doc2", "Document 2", "/path/to/doc2.pdf")
        
        # Add chunks
        db.add_chunk("doc1", "Content from document 1", 0, 22, 1)
        db.add_chunk("doc1", "More content from doc 1", 23, 46, 1)
        db.add_chunk("doc2", "Content from document 2", 0, 22, 1)
        
        # Test statistics
        stats = ingester.get_ingestion_stats()
        assert stats["documents"] == 2
        assert stats["chunks"] == 3
        assert stats["average_chunks_per_doc"] == 1.5
        
        # Test document listing
        documents = db.list_documents()
        assert len(documents) == 2
        doc_ids = {doc["doc_id"] for doc in documents}
        assert "doc1" in doc_ids
        assert "doc2" in doc_ids
        
        # Test document deletion
        result = db.delete_document("doc1")
        assert result is True
        
        # Verify deletion
        remaining_docs = db.list_documents()
        assert len(remaining_docs) == 1
        assert remaining_docs[0]["doc_id"] == "doc2"
        
        # Verify chunks were also deleted
        doc1_chunks = db.get_document_chunks("doc1")
        assert len(doc1_chunks) == 0
        
        db.close()
    
    def test_chunking_with_overlap(self, temp_db_path):
        """Test that chunking with overlap works correctly."""
        # Initialize components
        db = CorpusDatabase(temp_db_path)
        db.initialize_schema()
        
        # Create chunker with specific settings
        chunker = TextChunker(chunk_size=100, overlap_size=20)
        
        # Create long text that will require multiple chunks
        long_text = "This is a test sentence. " * 20  # About 500 characters
        
        chunks = chunker.chunk_text(long_text, doc_id="test_doc")
        
        # Should create multiple chunks
        assert len(chunks) > 1
        
        # Verify overlap between consecutive chunks
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]
            next_chunk = chunks[i + 1]
            
            # There should be some overlap or reasonable gap
            gap = next_chunk.start_offset - current_chunk.end_offset
            assert gap <= chunker.overlap_size
            
            # Chunks should not be empty
            assert len(current_chunk.text.strip()) > 0
            assert len(next_chunk.text.strip()) > 0
        
        db.close()
    
    def test_error_handling(self, temp_db_path):
        """Test error handling in various scenarios."""
        # Initialize components
        db = CorpusDatabase(temp_db_path)
        db.initialize_schema()
        
        extractor = PDFExtractor()
        chunker = TextChunker()
        ingester = DocumentIngester(db, extractor, chunker)
        
        # Test ingestion of non-existent file
        with pytest.raises(FileNotFoundError):
            ingester.ingest_pdf("nonexistent.pdf")
        
        # Test search in empty database
        results = db.search("anything")
        assert results == []
        
        # Test getting info for non-existent document
        doc_info = db.get_document_info("nonexistent")
        assert doc_info is None
        
        # Test validation of non-existent document
        validation = ingester.validate_ingestion("nonexistent")
        assert validation["valid"] is False
        assert "Document not found" in validation["error"]
        
        db.close()