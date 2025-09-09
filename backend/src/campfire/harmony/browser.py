"""
Local browser tool implementation for document search and retrieval.

This module provides the actual implementation of the browser tool methods
that are configured in browser_tool.py. It interfaces with the corpus database
to provide search, open, and find functionality for the Harmony tool system.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from ..corpus.database import CorpusDatabase

logger = logging.getLogger(__name__)


class LocalBrowserTool:
    """Local browser tool for document corpus interaction."""
    
    def __init__(self, db_path: str | Path):
        """Initialize browser tool with database connection.
        
        Args:
            db_path: Path to the corpus SQLite database
        """
        self.db = CorpusDatabase(db_path)
        
    def search(self, q: str, k: int = 5) -> Dict[str, Any]:
        """Search the local document corpus for relevant information.
        
        Args:
            q: Search query for finding relevant documents
            k: Number of results to return (default: 5)
            
        Returns:
            Dictionary with search results and metadata
        """
        try:
            # Perform FTS5 search
            results = self.db.search(q, limit=k)
            
            # Format results for tool response
            formatted_results = []
            for result in results:
                # Create snippet with context
                snippet = self._create_snippet(result["text"], q)
                
                formatted_results.append({
                    "doc_id": result["doc_id"],
                    "doc_title": result["doc_title"],
                    "snippet": snippet,
                    "location": {
                        "start_offset": result["start_offset"],
                        "end_offset": result["end_offset"],
                        "page_number": result["page_number"]
                    },
                    "relevance_score": result.get("rank", 0)
                })
            
            return {
                "status": "success",
                "query": q,
                "total_results": len(formatted_results),
                "results": formatted_results
            }
            
        except Exception as e:
            logger.error(f"Search failed for query '{q}': {e}")
            return {
                "status": "error",
                "query": q,
                "error": str(e),
                "results": []
            }
    
    def open(self, doc_id: str, start: int, end: int) -> Dict[str, Any]:
        """Open and retrieve a specific text window from a document.
        
        Args:
            doc_id: Document identifier from search results
            start: Start position/offset in the document
            end: End position/offset in the document
            
        Returns:
            Dictionary with text content and metadata
        """
        try:
            # Get document info first to check if document exists
            doc_info = self.db.get_document_info(doc_id)
            if not doc_info:
                return {
                    "status": "error",
                    "doc_id": doc_id,
                    "error": "Document not found",
                    "text": ""
                }
            
            # Get chunks that overlap with the requested range
            chunks = self.db.get_document_chunks(
                doc_id=doc_id,
                start_offset=start,
                end_offset=end
            )
            
            if not chunks:
                return {
                    "status": "error",
                    "doc_id": doc_id,
                    "error": f"No content found for range {start}-{end}",
                    "text": ""
                }
            
            # Combine overlapping chunks into continuous text
            combined_text = self._combine_chunks(chunks, start, end)
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "doc_title": doc_info["title"],
                "text": combined_text,
                "location": {
                    "start_offset": start,
                    "end_offset": end,
                    "actual_start": chunks[0]["start_offset"] if chunks else start,
                    "actual_end": chunks[-1]["end_offset"] if chunks else end
                },
                "chunk_count": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"Open failed for doc_id '{doc_id}' range {start}-{end}: {e}")
            return {
                "status": "error",
                "doc_id": doc_id,
                "error": str(e),
                "text": ""
            }
    
    def find(self, doc_id: str, pattern: str, after: int) -> Dict[str, Any]:
        """Find specific patterns within a document from a given position.
        
        Args:
            doc_id: Document identifier to search within
            pattern: Text pattern to search for
            after: Position to start searching from
            
        Returns:
            Dictionary with found matches and their locations
        """
        try:
            # Get chunks starting from the 'after' position
            chunks = self.db.get_document_chunks(
                doc_id=doc_id,
                start_offset=after
            )
            
            if not chunks:
                return {
                    "status": "success",
                    "doc_id": doc_id,
                    "pattern": pattern,
                    "matches": [],
                    "total_matches": 0
                }
            
            # Get document info
            doc_info = self.db.get_document_info(doc_id)
            doc_title = doc_info["title"] if doc_info else "Unknown"
            
            # Search for pattern in chunks
            matches = []
            for chunk in chunks:
                chunk_matches = self._find_pattern_in_chunk(
                    chunk, pattern, after
                )
                matches.extend(chunk_matches)
            
            # Sort matches by position
            matches.sort(key=lambda x: x["location"]["start_offset"])
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "doc_title": doc_title,
                "pattern": pattern,
                "search_after": after,
                "matches": matches,
                "total_matches": len(matches)
            }
            
        except Exception as e:
            logger.error(f"Find failed for doc_id '{doc_id}' pattern '{pattern}': {e}")
            return {
                "status": "error",
                "doc_id": doc_id,
                "pattern": pattern,
                "error": str(e),
                "matches": []
            }
    
    def _create_snippet(self, text: str, query: str, max_length: int = 200) -> str:
        """Create a snippet from text highlighting the query terms.
        
        Args:
            text: Full text content
            query: Search query
            max_length: Maximum snippet length
            
        Returns:
            Formatted snippet with query terms highlighted
        """
        # Find the best position to center the snippet
        query_terms = query.lower().split()
        text_lower = text.lower()
        
        # Find first occurrence of any query term
        best_pos = 0
        for term in query_terms:
            pos = text_lower.find(term)
            if pos != -1:
                best_pos = pos
                break
        
        # Calculate snippet boundaries
        snippet_start = max(0, best_pos - max_length // 2)
        snippet_end = min(len(text), snippet_start + max_length)
        
        # Adjust start to avoid cutting words
        if snippet_start > 0:
            while snippet_start < len(text) and text[snippet_start] != ' ':
                snippet_start += 1
            snippet_start = min(snippet_start + 1, len(text))
        
        # Adjust end to avoid cutting words
        if snippet_end < len(text):
            while snippet_end > snippet_start and text[snippet_end] != ' ':
                snippet_end -= 1
        
        snippet = text[snippet_start:snippet_end]
        
        # Add ellipsis if truncated
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(text):
            snippet = snippet + "..."
            
        return snippet.strip()
    
    def _combine_chunks(self, chunks: List[Dict[str, Any]], start: int, end: int) -> str:
        """Combine overlapping chunks into continuous text.
        
        Args:
            chunks: List of chunk dictionaries
            start: Requested start position
            end: Requested end position
            
        Returns:
            Combined text content
        """
        if not chunks:
            return ""
        
        # Sort chunks by start offset
        sorted_chunks = sorted(chunks, key=lambda x: x["start_offset"])
        
        # Combine text, handling overlaps
        combined_parts = []
        last_end = 0
        
        for chunk in sorted_chunks:
            chunk_start = chunk["start_offset"]
            chunk_end = chunk["end_offset"]
            chunk_text = chunk["text"]
            
            # Skip if this chunk is entirely before our range
            if chunk_end <= start:
                continue
                
            # Stop if this chunk starts after our range
            if chunk_start >= end:
                break
            
            # Trim chunk text to fit within requested range
            if chunk_start < start:
                # Chunk starts before our range, trim the beginning
                trim_chars = start - chunk_start
                chunk_text = chunk_text[trim_chars:]
                chunk_start = start
                
            if chunk_end > end:
                # Chunk extends beyond our range, trim the end
                trim_chars = chunk_end - end
                chunk_text = chunk_text[:-trim_chars] if trim_chars > 0 else chunk_text
                chunk_end = end
            
            # Add gap if there's a space between chunks
            if chunk_start > last_end and combined_parts:
                combined_parts.append(" [...] ")
            
            combined_parts.append(chunk_text)
            last_end = chunk_end
        
        return "".join(combined_parts)
    
    def _find_pattern_in_chunk(
        self, 
        chunk: Dict[str, Any], 
        pattern: str, 
        after: int
    ) -> List[Dict[str, Any]]:
        """Find pattern matches within a single chunk.
        
        Args:
            chunk: Chunk dictionary with text and metadata
            pattern: Pattern to search for
            after: Only include matches after this position
            
        Returns:
            List of match dictionaries
        """
        matches = []
        chunk_text = chunk["text"]
        chunk_start = chunk["start_offset"]
        
        # Use case-insensitive regex search
        try:
            for match in re.finditer(re.escape(pattern), chunk_text, re.IGNORECASE):
                match_start = chunk_start + match.start()
                match_end = chunk_start + match.end()
                
                # Only include matches after the specified position
                if match_start >= after:
                    # Create context snippet around the match
                    context_start = max(0, match.start() - 50)
                    context_end = min(len(chunk_text), match.end() + 50)
                    context = chunk_text[context_start:context_end]
                    
                    matches.append({
                        "text": match.group(),
                        "context": context,
                        "location": {
                            "start_offset": match_start,
                            "end_offset": match_end,
                            "page_number": chunk.get("page_number")
                        }
                    })
        except re.error as e:
            logger.warning(f"Regex error for pattern '{pattern}': {e}")
            # Fallback to simple string search
            pattern_lower = pattern.lower()
            text_lower = chunk_text.lower()
            
            start_pos = 0
            while True:
                pos = text_lower.find(pattern_lower, start_pos)
                if pos == -1:
                    break
                    
                match_start = chunk_start + pos
                match_end = match_start + len(pattern)
                
                if match_start >= after:
                    context_start = max(0, pos - 50)
                    context_end = min(len(chunk_text), pos + len(pattern) + 50)
                    context = chunk_text[context_start:context_end]
                    
                    matches.append({
                        "text": chunk_text[pos:pos + len(pattern)],
                        "context": context,
                        "location": {
                            "start_offset": match_start,
                            "end_offset": match_end,
                            "page_number": chunk.get("page_number")
                        }
                    })
                
                start_pos = pos + 1
        
        return matches
    
    def close(self):
        """Close database connection."""
        self.db.close()