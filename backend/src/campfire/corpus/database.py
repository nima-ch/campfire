"""
SQLite database management for document corpus with FTS5 support.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class CorpusDatabase:
    """Manages SQLite database with FTS5 for document corpus."""
    
    def __init__(self, db_path: str | Path):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        
    def connect(self) -> sqlite3.Connection:
        """Get database connection, creating if needed."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
            # Enable FTS5
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def initialize_schema(self):
        """Create database tables and FTS5 virtual table."""
        conn = self.connect()
        
        # Documents table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Text chunks with position tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                rowid INTEGER PRIMARY KEY,
                doc_id TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                page_number INTEGER,
                text TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES docs (doc_id)
            )
        """)
        
        # FTS5 virtual table for full-text search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                text,
                doc_id UNINDEXED,
                content='chunks',
                content_rowid='rowid'
            )
        """)
        
        # Triggers to keep FTS5 in sync
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, text, doc_id) 
                VALUES (new.rowid, new.text, new.doc_id);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, text, doc_id) 
                VALUES('delete', old.rowid, old.text, old.doc_id);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, text, doc_id) 
                VALUES('delete', old.rowid, old.text, old.doc_id);
                INSERT INTO chunks_fts(rowid, text, doc_id) 
                VALUES (new.rowid, new.text, new.doc_id);
            END
        """)
        
        conn.commit()
        logger.info("Database schema initialized")
    
    def add_document(self, doc_id: str, title: str, path: str) -> bool:
        """Add document metadata to database.
        
        Args:
            doc_id: Unique document identifier
            title: Document title
            path: File path to document
            
        Returns:
            True if added successfully, False if already exists
        """
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO docs (doc_id, title, path) VALUES (?, ?, ?)",
                (doc_id, title, path)
            )
            conn.commit()
            logger.info(f"Added document: {doc_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Document already exists: {doc_id}")
            return False
    
    def add_chunk(
        self, 
        doc_id: str, 
        text: str, 
        start_offset: int, 
        end_offset: int,
        page_number: Optional[int] = None
    ) -> int:
        """Add text chunk to database.
        
        Args:
            doc_id: Document identifier
            text: Chunk text content
            start_offset: Start position in original document
            end_offset: End position in original document
            page_number: Page number (optional)
            
        Returns:
            Row ID of inserted chunk
        """
        conn = self.connect()
        cursor = conn.execute(
            """INSERT INTO chunks (doc_id, text, start_offset, end_offset, page_number)
               VALUES (?, ?, ?, ?, ?)""",
            (doc_id, text, start_offset, end_offset, page_number)
        )
        conn.commit()
        return cursor.lastrowid
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search documents using FTS5.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of search results with metadata
        """
        conn = self.connect()
        
        # Sanitize query for FTS5 - remove punctuation and special characters
        import re
        sanitized_query = re.sub(r'[^\w\s]', ' ', query)  # Replace punctuation with spaces
        sanitized_query = re.sub(r'\s+', ' ', sanitized_query).strip()  # Normalize whitespace
        
        if not sanitized_query:
            return []
        
        # Convert multi-word queries to OR syntax for better matching
        query_terms = [term.strip() for term in sanitized_query.split() if term.strip()]
        if len(query_terms) > 1:
            fts_query = " OR ".join(f'"{term}"' for term in query_terms)  # Quote each term
        else:
            fts_query = f'"{query_terms[0]}"' if query_terms else ""
        
        if not fts_query:
            return []
        
        cursor = conn.execute("""
            SELECT 
                c.rowid,
                c.doc_id,
                c.text,
                c.start_offset,
                c.end_offset,
                c.page_number,
                d.title,
                d.path,
                rank
            FROM chunks_fts 
            JOIN chunks c ON chunks_fts.rowid = c.rowid
            JOIN docs d ON c.doc_id = d.doc_id
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "chunk_id": row["rowid"],
                "doc_id": row["doc_id"],
                "text": row["text"],
                "start_offset": row["start_offset"],
                "end_offset": row["end_offset"],
                "page_number": row["page_number"],
                "doc_title": row["title"],
                "doc_path": row["path"],
                "rank": row["rank"]
            })
        
        return results
    
    def get_chunk_by_id(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """Get specific chunk by ID.
        
        Args:
            chunk_id: Chunk row ID
            
        Returns:
            Chunk data or None if not found
        """
        conn = self.connect()
        cursor = conn.execute("""
            SELECT 
                c.rowid,
                c.doc_id,
                c.text,
                c.start_offset,
                c.end_offset,
                c.page_number,
                d.title,
                d.path
            FROM chunks c
            JOIN docs d ON c.doc_id = d.doc_id
            WHERE c.rowid = ?
        """, (chunk_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                "chunk_id": row["rowid"],
                "doc_id": row["doc_id"],
                "text": row["text"],
                "start_offset": row["start_offset"],
                "end_offset": row["end_offset"],
                "page_number": row["page_number"],
                "doc_title": row["title"],
                "doc_path": row["path"]
            }
        return None
    
    def get_document_chunks(
        self, 
        doc_id: str, 
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get chunks from specific document, optionally within offset range.
        
        Args:
            doc_id: Document identifier
            start_offset: Optional start position filter
            end_offset: Optional end position filter
            
        Returns:
            List of chunks matching criteria
        """
        conn = self.connect()
        
        query = """
            SELECT 
                c.rowid,
                c.doc_id,
                c.text,
                c.start_offset,
                c.end_offset,
                c.page_number,
                d.title,
                d.path
            FROM chunks c
            JOIN docs d ON c.doc_id = d.doc_id
            WHERE c.doc_id = ?
        """
        params = [doc_id]
        
        if start_offset is not None:
            query += " AND c.end_offset >= ?"
            params.append(start_offset)
            
        if end_offset is not None:
            query += " AND c.start_offset <= ?"
            params.append(end_offset)
            
        query += " ORDER BY c.start_offset"
        
        cursor = conn.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "chunk_id": row["rowid"],
                "doc_id": row["doc_id"],
                "text": row["text"],
                "start_offset": row["start_offset"],
                "end_offset": row["end_offset"],
                "page_number": row["page_number"],
                "doc_title": row["title"],
                "doc_path": row["path"]
            })
        
        return results
    
    def get_document_info(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Document info or None if not found
        """
        conn = self.connect()
        cursor = conn.execute(
            "SELECT doc_id, title, path, created_at FROM docs WHERE doc_id = ?",
            (doc_id,)
        )
        
        row = cursor.fetchone()
        if row:
            return {
                "doc_id": row["doc_id"],
                "title": row["title"],
                "path": row["path"],
                "created_at": row["created_at"]
            }
        return None
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents in corpus.
        
        Returns:
            List of document metadata
        """
        conn = self.connect()
        cursor = conn.execute(
            "SELECT doc_id, title, path, created_at FROM docs ORDER BY title"
        )
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "doc_id": row["doc_id"],
                "title": row["title"],
                "path": row["path"],
                "created_at": row["created_at"]
            })
        
        return results
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document and all its chunks.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if deleted, False if not found
        """
        conn = self.connect()
        
        # Delete chunks first (triggers will handle FTS5)
        cursor = conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        chunks_deleted = cursor.rowcount
        
        # Delete document
        cursor = conn.execute("DELETE FROM docs WHERE doc_id = ?", (doc_id,))
        doc_deleted = cursor.rowcount > 0
        
        conn.commit()
        
        if doc_deleted:
            logger.info(f"Deleted document {doc_id} with {chunks_deleted} chunks")
        
        return doc_deleted
    
    def get_stats(self) -> Dict[str, int]:
        """Get corpus statistics.
        
        Returns:
            Dictionary with document and chunk counts
        """
        conn = self.connect()
        
        doc_count = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        
        return {
            "documents": doc_count,
            "chunks": chunk_count
        }