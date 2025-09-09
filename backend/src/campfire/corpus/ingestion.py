"""
Document ingestion pipeline with metadata preservation.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import hashlib
from datetime import datetime

from .database import CorpusDatabase
from .extractor import PDFExtractor, TextSegment
from .chunker import TextChunker, TextChunk

logger = logging.getLogger(__name__)


class DocumentIngester:
    """Orchestrates document ingestion pipeline."""
    
    def __init__(
        self,
        database: CorpusDatabase,
        extractor: Optional[PDFExtractor] = None,
        chunker: Optional[TextChunker] = None
    ):
        """Initialize document ingester.
        
        Args:
            database: CorpusDatabase instance
            extractor: PDFExtractor instance (creates default if None)
            chunker: TextChunker instance (creates default if None)
        """
        self.database = database
        self.extractor = extractor or PDFExtractor()
        self.chunker = chunker or TextChunker()
    
    def ingest_pdf(
        self,
        pdf_path: str | Path,
        doc_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ingest PDF document into corpus.
        
        Args:
            pdf_path: Path to PDF file
            doc_id: Optional document ID (generates from filename if None)
            title: Optional document title (uses filename if None)
            metadata: Optional additional metadata
            
        Returns:
            Dictionary with ingestion results
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            Exception: If ingestion fails
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Generate doc_id and title if not provided
        if doc_id is None:
            doc_id = self._generate_doc_id(pdf_path)
        
        if title is None:
            title = pdf_path.stem
        
        logger.info(f"Starting ingestion of {pdf_path} as {doc_id}")
        
        try:
            # Check if document already exists
            existing_doc = self.database.get_document_info(doc_id)
            if existing_doc:
                logger.warning(f"Document {doc_id} already exists, skipping")
                return {
                    "doc_id": doc_id,
                    "status": "skipped",
                    "reason": "already_exists",
                    "existing_doc": existing_doc
                }
            
            # Extract text segments from PDF
            logger.info(f"Extracting text from {pdf_path}")
            segments = self.extractor.extract_text_segments(pdf_path)
            
            if not segments:
                logger.warning(f"No text extracted from {pdf_path}")
                return {
                    "doc_id": doc_id,
                    "status": "failed",
                    "reason": "no_text_extracted"
                }
            
            # Add document to database
            self.database.add_document(doc_id, title, str(pdf_path))
            
            # Chunk text using segments
            logger.info(f"Chunking text into segments")
            chunks = self.chunker.chunk_with_segments(segments, doc_id)
            
            # Merge small chunks if needed
            chunks = self.chunker.merge_small_chunks(chunks)
            
            # Add chunks to database
            chunk_ids = []
            for chunk in chunks:
                # Determine primary page number (most common page in chunk)
                primary_page = None
                if chunk.page_numbers:
                    primary_page = chunk.page_numbers[0]  # Use first page as primary
                
                chunk_id = self.database.add_chunk(
                    doc_id=doc_id,
                    text=chunk.text,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    page_number=primary_page
                )
                chunk_ids.append(chunk_id)
            
            # Get document statistics
            doc_info = self.extractor.get_document_info(pdf_path)
            total_chars = sum(len(chunk.text) for chunk in chunks)
            
            result = {
                "doc_id": doc_id,
                "title": title,
                "status": "success",
                "file_info": {
                    "path": str(pdf_path),
                    "size": doc_info["file_size"],
                    "pages": doc_info["page_count"]
                },
                "extraction": {
                    "segments": len(segments),
                    "total_characters": doc_info["character_count"]
                },
                "chunking": {
                    "chunks": len(chunks),
                    "chunk_characters": total_chars,
                    "chunk_ids": chunk_ids
                },
                "metadata": metadata or {},
                "ingested_at": datetime.now().isoformat()
            }
            
            logger.info(f"Successfully ingested {doc_id}: {len(chunks)} chunks, {total_chars} characters")
            return result
            
        except Exception as e:
            logger.error(f"Failed to ingest {pdf_path}: {e}")
            # Clean up partial ingestion
            try:
                self.database.delete_document(doc_id)
            except:
                pass
            raise
    
    def ingest_directory(
        self,
        directory_path: str | Path,
        pattern: str = "*.pdf",
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """Ingest all PDF files from directory.
        
        Args:
            directory_path: Path to directory containing PDFs
            pattern: File pattern to match (default: *.pdf)
            recursive: Whether to search subdirectories
            
        Returns:
            List of ingestion results for each file
        """
        directory_path = Path(directory_path)
        
        if not directory_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Find PDF files
        if recursive:
            pdf_files = list(directory_path.rglob(pattern))
        else:
            pdf_files = list(directory_path.glob(pattern))
        
        logger.info(f"Found {len(pdf_files)} PDF files in {directory_path}")
        
        results = []
        for pdf_file in pdf_files:
            try:
                result = self.ingest_pdf(pdf_file)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to ingest {pdf_file}: {e}")
                results.append({
                    "doc_id": self._generate_doc_id(pdf_file),
                    "status": "failed",
                    "error": str(e),
                    "file_path": str(pdf_file)
                })
        
        successful = len([r for r in results if r["status"] == "success"])
        logger.info(f"Ingested {successful}/{len(results)} documents successfully")
        
        return results
    
    def reingest_document(self, doc_id: str, pdf_path: str | Path) -> Dict[str, Any]:
        """Re-ingest document, replacing existing version.
        
        Args:
            doc_id: Document ID to replace
            pdf_path: Path to new PDF file
            
        Returns:
            Ingestion result
        """
        logger.info(f"Re-ingesting document {doc_id}")
        
        # Get existing document info
        existing_doc = self.database.get_document_info(doc_id)
        title = existing_doc["title"] if existing_doc else None
        
        # Delete existing document
        if existing_doc:
            self.database.delete_document(doc_id)
            logger.info(f"Deleted existing document {doc_id}")
        
        # Ingest new version
        return self.ingest_pdf(pdf_path, doc_id=doc_id, title=title)
    
    def validate_ingestion(self, doc_id: str) -> Dict[str, Any]:
        """Validate that document was ingested correctly.
        
        Args:
            doc_id: Document ID to validate
            
        Returns:
            Validation results
        """
        doc_info = self.database.get_document_info(doc_id)
        if not doc_info:
            return {
                "doc_id": doc_id,
                "valid": False,
                "error": "Document not found"
            }
        
        # Get chunks
        chunks = self.database.get_document_chunks(doc_id)
        
        # Basic validation checks
        issues = []
        
        if not chunks:
            issues.append("No chunks found")
        
        # Check for gaps in offsets
        if len(chunks) > 1:
            sorted_chunks = sorted(chunks, key=lambda x: x["start_offset"])
            for i in range(1, len(sorted_chunks)):
                prev_end = sorted_chunks[i-1]["end_offset"]
                curr_start = sorted_chunks[i]["start_offset"]
                
                # Allow some gap for overlap, but not too much
                if curr_start > prev_end + 100:
                    issues.append(f"Large gap between chunks {i-1} and {i}")
        
        # Check for empty chunks
        empty_chunks = [c for c in chunks if not c["text"].strip()]
        if empty_chunks:
            issues.append(f"Found {len(empty_chunks)} empty chunks")
        
        # Test search functionality
        try:
            search_results = self.database.search("emergency", limit=1)
            search_works = len(search_results) >= 0  # Even 0 results means search works
        except Exception as e:
            search_works = False
            issues.append(f"Search test failed: {e}")
        
        return {
            "doc_id": doc_id,
            "valid": len(issues) == 0,
            "document_info": doc_info,
            "chunk_count": len(chunks),
            "issues": issues,
            "search_functional": search_works,
            "validation_timestamp": datetime.now().isoformat()
        }
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get overall corpus ingestion statistics.
        
        Returns:
            Dictionary with corpus statistics
        """
        stats = self.database.get_stats()
        documents = self.database.list_documents()
        
        # Calculate additional stats
        total_size = 0
        total_pages = 0
        
        for doc in documents:
            try:
                if Path(doc["path"]).exists():
                    doc_info = self.extractor.get_document_info(doc["path"])
                    total_size += doc_info["file_size"]
                    total_pages += doc_info["page_count"]
            except:
                continue
        
        return {
            "documents": stats["documents"],
            "chunks": stats["chunks"],
            "total_file_size": total_size,
            "total_pages": total_pages,
            "average_chunks_per_doc": stats["chunks"] / max(1, stats["documents"]),
            "documents_list": documents
        }
    
    def _generate_doc_id(self, pdf_path: Path) -> str:
        """Generate document ID from file path.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Generated document ID
        """
        # Use filename without extension as base
        base_name = pdf_path.stem
        
        # Add hash of full path for uniqueness
        path_hash = hashlib.md5(str(pdf_path).encode()).hexdigest()[:8]
        
        return f"{base_name}_{path_hash}"
    
    def cleanup_orphaned_chunks(self) -> int:
        """Remove chunks that reference non-existent documents.
        
        Returns:
            Number of orphaned chunks removed
        """
        # This would be implemented if needed for maintenance
        # For now, foreign key constraints should prevent orphaned chunks
        return 0