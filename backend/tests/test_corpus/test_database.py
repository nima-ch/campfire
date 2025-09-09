"""
Tests for CorpusDatabase class.
"""

import pytest
import tempfile
from pathlib import Path
import sqlite3

from campfire.corpus.database import CorpusDatabase


class TestCorpusDatabase:
    """Test cases for CorpusDatabase."""
    
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
    
    def test_database_initialization(self, temp_db):
        """Test database schema initialization."""
        conn = temp_db.connect()
        
        # Check that tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        
        assert 'docs' in tables
        assert 'chunks' in tables
        assert 'chunks_fts' in tables
    
    def test_add_document(self, temp_db):
        """Test adding documents."""
        # Add new document
        result = temp_db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        assert result is True
        
        # Try to add duplicate
        result = temp_db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        assert result is False
        
        # Verify document exists
        doc_info = temp_db.get_document_info("test_doc")
        assert doc_info is not None
        assert doc_info["doc_id"] == "test_doc"
        assert doc_info["title"] == "Test Document"
        assert doc_info["path"] == "/path/to/test.pdf"
    
    def test_add_chunk(self, temp_db):
        """Test adding text chunks."""
        # Add document first
        temp_db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        
        # Add chunk
        chunk_id = temp_db.add_chunk(
            doc_id="test_doc",
            text="This is a test chunk of text.",
            start_offset=0,
            end_offset=29,
            page_number=1
        )
        
        assert chunk_id is not None
        assert isinstance(chunk_id, int)
        
        # Verify chunk exists
        chunk = temp_db.get_chunk_by_id(chunk_id)
        assert chunk is not None
        assert chunk["text"] == "This is a test chunk of text."
        assert chunk["start_offset"] == 0
        assert chunk["end_offset"] == 29
        assert chunk["page_number"] == 1
    
    def test_search_functionality(self, temp_db):
        """Test FTS5 search functionality."""
        # Add document and chunks
        temp_db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        
        chunk1_id = temp_db.add_chunk(
            doc_id="test_doc",
            text="Emergency procedures for fire safety.",
            start_offset=0,
            end_offset=37,
            page_number=1
        )
        
        chunk2_id = temp_db.add_chunk(
            doc_id="test_doc", 
            text="First aid treatment for burns and injuries.",
            start_offset=38,
            end_offset=81,
            page_number=1
        )
        
        # Search for "emergency"
        results = temp_db.search("emergency")
        assert len(results) == 1
        assert results[0]["chunk_id"] == chunk1_id
        assert "Emergency procedures" in results[0]["text"]
        
        # Search for "first aid"
        results = temp_db.search("first aid")
        assert len(results) == 1
        assert results[0]["chunk_id"] == chunk2_id
        
        # Search for non-existent term
        results = temp_db.search("nonexistent")
        assert len(results) == 0
    
    def test_get_document_chunks(self, temp_db):
        """Test retrieving chunks for a document."""
        # Add document and chunks
        temp_db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        
        chunk1_id = temp_db.add_chunk(
            doc_id="test_doc",
            text="First chunk",
            start_offset=0,
            end_offset=11,
            page_number=1
        )
        
        chunk2_id = temp_db.add_chunk(
            doc_id="test_doc",
            text="Second chunk", 
            start_offset=12,
            end_offset=24,
            page_number=1
        )
        
        # Get all chunks
        chunks = temp_db.get_document_chunks("test_doc")
        assert len(chunks) == 2
        
        # Get chunks in offset range
        chunks = temp_db.get_document_chunks("test_doc", start_offset=10, end_offset=20)
        assert len(chunks) == 2  # Both chunks overlap with range
        
        # Get chunks with no overlap
        chunks = temp_db.get_document_chunks("test_doc", start_offset=100, end_offset=200)
        assert len(chunks) == 0
    
    def test_delete_document(self, temp_db):
        """Test document deletion."""
        # Add document and chunks
        temp_db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        chunk_id = temp_db.add_chunk(
            doc_id="test_doc",
            text="Test chunk",
            start_offset=0,
            end_offset=10,
            page_number=1
        )
        
        # Verify document and chunk exist
        assert temp_db.get_document_info("test_doc") is not None
        assert temp_db.get_chunk_by_id(chunk_id) is not None
        
        # Delete document
        result = temp_db.delete_document("test_doc")
        assert result is True
        
        # Verify document and chunks are gone
        assert temp_db.get_document_info("test_doc") is None
        assert temp_db.get_chunk_by_id(chunk_id) is None
        
        # Try to delete non-existent document
        result = temp_db.delete_document("nonexistent")
        assert result is False
    
    def test_list_documents(self, temp_db):
        """Test listing all documents."""
        # Initially empty
        docs = temp_db.list_documents()
        assert len(docs) == 0
        
        # Add documents
        temp_db.add_document("doc1", "Document 1", "/path/to/doc1.pdf")
        temp_db.add_document("doc2", "Document 2", "/path/to/doc2.pdf")
        
        # List documents
        docs = temp_db.list_documents()
        assert len(docs) == 2
        
        doc_ids = {doc["doc_id"] for doc in docs}
        assert "doc1" in doc_ids
        assert "doc2" in doc_ids
    
    def test_get_stats(self, temp_db):
        """Test corpus statistics."""
        # Initially empty
        stats = temp_db.get_stats()
        assert stats["documents"] == 0
        assert stats["chunks"] == 0
        
        # Add document and chunks
        temp_db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        temp_db.add_chunk("test_doc", "Chunk 1", 0, 7, 1)
        temp_db.add_chunk("test_doc", "Chunk 2", 8, 15, 1)
        
        # Check stats
        stats = temp_db.get_stats()
        assert stats["documents"] == 1
        assert stats["chunks"] == 2
    
    def test_fts_triggers(self, temp_db):
        """Test that FTS5 triggers work correctly."""
        # Add document and chunk
        temp_db.add_document("test_doc", "Test Document", "/path/to/test.pdf")
        chunk_id = temp_db.add_chunk(
            doc_id="test_doc",
            text="Emergency response procedures",
            start_offset=0,
            end_offset=28,
            page_number=1
        )
        
        # Search should find the chunk
        results = temp_db.search("emergency")
        assert len(results) == 1
        
        # Delete chunk
        conn = temp_db.connect()
        conn.execute("DELETE FROM chunks WHERE rowid = ?", (chunk_id,))
        conn.commit()
        
        # Search should not find the chunk anymore
        results = temp_db.search("emergency")
        assert len(results) == 0