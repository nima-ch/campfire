"""
Text chunking system with configurable window size and overlap.
"""

from typing import List, Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class TextChunk:
    """Represents a chunk of text with position and metadata."""
    
    def __init__(
        self,
        text: str,
        start_offset: int,
        end_offset: int,
        chunk_index: int,
        page_numbers: Optional[List[int]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.text = text
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.chunk_index = chunk_index
        self.page_numbers = page_numbers or []
        self.metadata = metadata or {}
    
    def __repr__(self) -> str:
        return f"TextChunk(index={self.chunk_index}, offset={self.start_offset}-{self.end_offset}, pages={self.page_numbers})"
    
    def __len__(self) -> int:
        return len(self.text)


class TextChunker:
    """Chunks text with configurable window size and overlap."""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        overlap_size: int = 200,
        respect_sentences: bool = True,
        min_chunk_size: int = 100
    ):
        """Initialize text chunker.
        
        Args:
            chunk_size: Target size for each chunk in characters
            overlap_size: Number of characters to overlap between chunks
            respect_sentences: Whether to try to break at sentence boundaries
            min_chunk_size: Minimum chunk size to avoid tiny chunks
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.respect_sentences = respect_sentences
        self.min_chunk_size = min_chunk_size
        
        # Sentence boundary patterns
        self.sentence_endings = re.compile(r'[.!?]+\s+')
        self.paragraph_breaks = re.compile(r'\n\s*\n')
    
    def chunk_text(self, text: str, doc_id: str = None) -> List[TextChunk]:
        """Chunk text into overlapping segments.
        
        Args:
            text: Text content to chunk
            doc_id: Optional document identifier for metadata
            
        Returns:
            List of TextChunk objects
        """
        if not text or len(text) < self.min_chunk_size:
            if text:
                return [TextChunk(
                    text=text,
                    start_offset=0,
                    end_offset=len(text),
                    chunk_index=0,
                    metadata={"doc_id": doc_id} if doc_id else {}
                )]
            return []
        
        chunks = []
        chunk_index = 0
        start_pos = 0
        
        while start_pos < len(text):
            # Calculate end position for this chunk
            end_pos = min(start_pos + self.chunk_size, len(text))
            
            # If we're not at the end and respecting sentences, try to break at sentence boundary
            if end_pos < len(text) and self.respect_sentences:
                end_pos = self._find_sentence_boundary(text, start_pos, end_pos)
            
            # Extract chunk text
            chunk_text = text[start_pos:end_pos].strip()
            
            # Skip empty chunks
            if not chunk_text:
                start_pos = end_pos
                continue
            
            # Create chunk
            chunk = TextChunk(
                text=chunk_text,
                start_offset=start_pos,
                end_offset=start_pos + len(chunk_text),
                chunk_index=chunk_index,
                metadata={"doc_id": doc_id} if doc_id else {}
            )
            chunks.append(chunk)
            
            chunk_index += 1
            
            # Calculate next start position with overlap
            if end_pos >= len(text):
                break
                
            # Move start position forward, accounting for overlap
            next_start = end_pos - self.overlap_size
            
            # Ensure we make progress
            if next_start <= start_pos:
                next_start = start_pos + max(1, self.chunk_size // 2)
            
            start_pos = next_start
        
        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks
    
    def _find_sentence_boundary(self, text: str, start_pos: int, target_end: int) -> int:
        """Find the best sentence boundary near target end position.
        
        Args:
            text: Full text
            start_pos: Start position of current chunk
            target_end: Target end position
            
        Returns:
            Adjusted end position at sentence boundary
        """
        # Look for sentence endings within a reasonable range before target_end
        search_start = max(start_pos + self.min_chunk_size, target_end - 200)
        search_end = min(len(text), target_end + 100)
        
        search_text = text[search_start:search_end]
        
        # Find all sentence endings in the search range
        sentence_matches = list(self.sentence_endings.finditer(search_text))
        
        if sentence_matches:
            # Find the sentence ending closest to our target
            best_match = None
            best_distance = float('inf')
            
            for match in sentence_matches:
                abs_pos = search_start + match.end()
                distance = abs(abs_pos - target_end)
                
                # Prefer positions before target_end, but not too far
                if abs_pos <= target_end + 50:
                    if distance < best_distance:
                        best_distance = distance
                        best_match = match
            
            if best_match:
                return search_start + best_match.end()
        
        # Fallback: look for paragraph breaks
        paragraph_matches = list(self.paragraph_breaks.finditer(search_text))
        if paragraph_matches:
            for match in paragraph_matches:
                abs_pos = search_start + match.end()
                if abs_pos <= target_end + 50:
                    return abs_pos
        
        # No good boundary found, use target_end
        return target_end
    
    def chunk_with_segments(
        self, 
        segments: List[Any], 
        doc_id: str = None
    ) -> List[TextChunk]:
        """Chunk text using pre-extracted segments with position info.
        
        Args:
            segments: List of TextSegment objects from PDFExtractor
            doc_id: Optional document identifier
            
        Returns:
            List of TextChunk objects with page information
        """
        if not segments:
            return []
        
        # Reconstruct full text and create page mapping
        full_text = ''.join(segment.text for segment in segments)
        
        # Create offset to page mapping
        offset_to_page = {}
        for segment in segments:
            for offset in range(segment.start_offset, segment.end_offset):
                offset_to_page[offset] = segment.page_number
        
        # Chunk the full text
        text_chunks = self.chunk_text(full_text, doc_id)
        
        # Add page information to chunks
        for chunk in text_chunks:
            # Find all pages that this chunk spans
            pages = set()
            for offset in range(chunk.start_offset, chunk.end_offset):
                if offset in offset_to_page:
                    pages.add(offset_to_page[offset])
            
            chunk.page_numbers = sorted(pages)
            
            # Add page info to metadata
            if pages:
                chunk.metadata.update({
                    "page_numbers": chunk.page_numbers,
                    "page_count": len(pages)
                })
        
        return text_chunks
    
    def merge_small_chunks(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Merge chunks that are smaller than minimum size.
        
        Args:
            chunks: List of TextChunk objects
            
        Returns:
            List with small chunks merged
        """
        if not chunks:
            return chunks
        
        merged_chunks = []
        current_chunk = None
        
        for chunk in chunks:
            if len(chunk.text) < self.min_chunk_size and current_chunk is not None:
                # Merge with previous chunk
                merged_text = current_chunk.text + " " + chunk.text
                merged_pages = sorted(set(current_chunk.page_numbers + chunk.page_numbers))
                
                current_chunk = TextChunk(
                    text=merged_text,
                    start_offset=current_chunk.start_offset,
                    end_offset=chunk.end_offset,
                    chunk_index=current_chunk.chunk_index,
                    page_numbers=merged_pages,
                    metadata={
                        **current_chunk.metadata,
                        "merged": True,
                        "original_chunks": [current_chunk.chunk_index, chunk.chunk_index]
                    }
                )
            else:
                # Add previous chunk if exists
                if current_chunk is not None:
                    merged_chunks.append(current_chunk)
                current_chunk = chunk
        
        # Add final chunk
        if current_chunk is not None:
            merged_chunks.append(current_chunk)
        
        # Reindex chunks
        for i, chunk in enumerate(merged_chunks):
            chunk.chunk_index = i
        
        logger.info(f"Merged {len(chunks)} chunks into {len(merged_chunks)} chunks")
        return merged_chunks
    
    def get_chunk_context(
        self, 
        chunks: List[TextChunk], 
        target_chunk_index: int,
        context_size: int = 1
    ) -> Dict[str, Any]:
        """Get context around a specific chunk.
        
        Args:
            chunks: List of all chunks
            target_chunk_index: Index of target chunk
            context_size: Number of chunks before/after to include
            
        Returns:
            Dictionary with chunk and context information
        """
        if not chunks or target_chunk_index >= len(chunks):
            return {}
        
        target_chunk = chunks[target_chunk_index]
        
        # Get context chunks
        start_idx = max(0, target_chunk_index - context_size)
        end_idx = min(len(chunks), target_chunk_index + context_size + 1)
        
        context_chunks = chunks[start_idx:end_idx]
        
        # Combine context text
        context_text = ' '.join(chunk.text for chunk in context_chunks)
        
        # Get all pages in context
        all_pages = set()
        for chunk in context_chunks:
            all_pages.update(chunk.page_numbers)
        
        return {
            "target_chunk": target_chunk,
            "context_chunks": context_chunks,
            "context_text": context_text,
            "pages": sorted(all_pages),
            "start_offset": context_chunks[0].start_offset,
            "end_offset": context_chunks[-1].end_offset
        }
    
    def split_by_sections(self, text: str, section_patterns: List[str]) -> List[Dict[str, Any]]:
        """Split text into sections based on patterns.
        
        Args:
            text: Text to split
            section_patterns: List of regex patterns for section headers
            
        Returns:
            List of section dictionaries with text and metadata
        """
        sections = []
        
        # Combine all patterns
        combined_pattern = '|'.join(f'({pattern})' for pattern in section_patterns)
        section_regex = re.compile(combined_pattern, re.MULTILINE | re.IGNORECASE)
        
        matches = list(section_regex.finditer(text))
        
        if not matches:
            # No sections found, return entire text as one section
            return [{
                "title": "Document",
                "text": text,
                "start_offset": 0,
                "end_offset": len(text),
                "section_index": 0
            }]
        
        # Process sections
        for i, match in enumerate(matches):
            section_start = match.start()
            section_title = match.group().strip()
            
            # Find section end (start of next section or end of text)
            if i + 1 < len(matches):
                section_end = matches[i + 1].start()
            else:
                section_end = len(text)
            
            section_text = text[section_start:section_end].strip()
            
            if section_text:
                sections.append({
                    "title": section_title,
                    "text": section_text,
                    "start_offset": section_start,
                    "end_offset": section_end,
                    "section_index": i
                })
        
        logger.info(f"Split text into {len(sections)} sections")
        return sections