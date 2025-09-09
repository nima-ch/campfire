"""
PDF text extraction with page and offset tracking using pdfminer.six.
"""

from pathlib import Path
from typing import List, Dict, Any, Iterator, Tuple
import logging

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTTextBox, LTTextLine, LTChar
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams

logger = logging.getLogger(__name__)


class TextSegment:
    """Represents a segment of text with position information."""
    
    def __init__(
        self, 
        text: str, 
        page_number: int, 
        start_offset: int, 
        end_offset: int,
        bbox: Tuple[float, float, float, float] = None
    ):
        self.text = text
        self.page_number = page_number
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.bbox = bbox  # (x0, y0, x1, y1) bounding box
    
    def __repr__(self) -> str:
        return f"TextSegment(page={self.page_number}, offset={self.start_offset}-{self.end_offset}, text='{self.text[:50]}...')"


class PDFExtractor:
    """Extracts text from PDF files with precise position tracking."""
    
    def __init__(self, preserve_layout: bool = True):
        """Initialize PDF extractor.
        
        Args:
            preserve_layout: Whether to preserve text layout and spacing
        """
        self.preserve_layout = preserve_layout
        self.laparams = LAParams(
            boxes_flow=0.5,
            word_margin=0.1,
            char_margin=2.0,
            line_margin=0.5
        ) if preserve_layout else None
    
    def extract_text_segments(self, pdf_path: str | Path) -> List[TextSegment]:
        """Extract text segments with position information.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of TextSegment objects with position data
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            Exception: If PDF processing fails
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        segments = []
        global_offset = 0
        
        try:
            with open(pdf_path, 'rb') as file:
                # Extract pages with layout analysis
                for page_num, page_layout in enumerate(extract_pages(file, laparams=self.laparams), 1):
                    page_text_elements = []
                    
                    # Extract text elements from page
                    for element in page_layout:
                        if isinstance(element, LTTextContainer):
                            text_elements = self._extract_text_elements(element)
                            page_text_elements.extend(text_elements)
                    
                    # Sort elements by reading order (top to bottom, left to right)
                    page_text_elements.sort(key=lambda x: (-x[1][3], x[1][0]))  # Sort by -y1, then x0
                    
                    # Create segments for this page
                    page_text = ""
                    for text, bbox in page_text_elements:
                        if text.strip():  # Only include non-empty text
                            start_offset = global_offset + len(page_text)
                            page_text += text
                            end_offset = global_offset + len(page_text)
                            
                            segment = TextSegment(
                                text=text,
                                page_number=page_num,
                                start_offset=start_offset,
                                end_offset=end_offset,
                                bbox=bbox
                            )
                            segments.append(segment)
                    
                    # Add page break
                    if page_text and not page_text.endswith('\n'):
                        page_text += '\n'
                    
                    global_offset += len(page_text)
                    
                    logger.debug(f"Extracted {len(page_text)} characters from page {page_num}")
            
            logger.info(f"Extracted {len(segments)} text segments from {pdf_path}")
            return segments
            
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            raise
    
    def _extract_text_elements(self, container: LTTextContainer) -> List[Tuple[str, Tuple[float, float, float, float]]]:
        """Extract text elements with bounding boxes from container.
        
        Args:
            container: LTTextContainer object
            
        Returns:
            List of (text, bbox) tuples
        """
        elements = []
        
        for element in container:
            if isinstance(element, LTTextBox):
                # Process text box
                box_text = element.get_text()
                if box_text.strip():
                    elements.append((box_text, element.bbox))
            elif isinstance(element, LTTextLine):
                # Process text line
                line_text = element.get_text()
                if line_text.strip():
                    elements.append((line_text, element.bbox))
            elif hasattr(element, 'get_text'):
                # Fallback for other text elements
                text = element.get_text()
                if text.strip():
                    bbox = getattr(element, 'bbox', (0, 0, 0, 0))
                    elements.append((text, bbox))
        
        return elements
    
    def extract_full_text(self, pdf_path: str | Path) -> str:
        """Extract complete text content from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Full text content as string
        """
        segments = self.extract_text_segments(pdf_path)
        return ''.join(segment.text for segment in segments)
    
    def extract_page_text(self, pdf_path: str | Path, page_number: int) -> str:
        """Extract text from specific page.
        
        Args:
            pdf_path: Path to PDF file
            page_number: Page number (1-based)
            
        Returns:
            Text content from specified page
        """
        segments = self.extract_text_segments(pdf_path)
        page_segments = [s for s in segments if s.page_number == page_number]
        return ''.join(segment.text for segment in page_segments)
    
    def get_text_at_offset(
        self, 
        pdf_path: str | Path, 
        start_offset: int, 
        end_offset: int
    ) -> Dict[str, Any]:
        """Get text content at specific offset range.
        
        Args:
            pdf_path: Path to PDF file
            start_offset: Start character position
            end_offset: End character position
            
        Returns:
            Dictionary with text content and metadata
        """
        segments = self.extract_text_segments(pdf_path)
        
        # Find segments that overlap with the requested range
        overlapping_segments = []
        for segment in segments:
            if (segment.start_offset < end_offset and 
                segment.end_offset > start_offset):
                overlapping_segments.append(segment)
        
        if not overlapping_segments:
            return {
                "text": "",
                "pages": [],
                "start_offset": start_offset,
                "end_offset": end_offset
            }
        
        # Extract text within the range
        full_text = ''.join(segment.text for segment in segments)
        extracted_text = full_text[start_offset:end_offset]
        
        # Get page numbers
        pages = sorted(set(segment.page_number for segment in overlapping_segments))
        
        return {
            "text": extracted_text,
            "pages": pages,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "segments": len(overlapping_segments)
        }
    
    def find_text_pattern(
        self, 
        pdf_path: str | Path, 
        pattern: str, 
        after_offset: int = 0,
        case_sensitive: bool = False
    ) -> List[Dict[str, Any]]:
        """Find text pattern in PDF after specified offset.
        
        Args:
            pdf_path: Path to PDF file
            pattern: Text pattern to search for
            after_offset: Start search after this offset
            case_sensitive: Whether search is case sensitive
            
        Returns:
            List of matches with position information
        """
        full_text = self.extract_full_text(pdf_path)
        
        if not case_sensitive:
            search_text = full_text.lower()
            search_pattern = pattern.lower()
        else:
            search_text = full_text
            search_pattern = pattern
        
        matches = []
        start_pos = after_offset
        
        while True:
            pos = search_text.find(search_pattern, start_pos)
            if pos == -1:
                break
            
            # Get context around match
            context_start = max(0, pos - 50)
            context_end = min(len(full_text), pos + len(pattern) + 50)
            context = full_text[context_start:context_end]
            
            # Find which page this match is on
            segments = self.extract_text_segments(pdf_path)
            page_number = None
            for segment in segments:
                if segment.start_offset <= pos < segment.end_offset:
                    page_number = segment.page_number
                    break
            
            matches.append({
                "pattern": pattern,
                "start_offset": pos,
                "end_offset": pos + len(pattern),
                "page_number": page_number,
                "context": context,
                "match_text": full_text[pos:pos + len(pattern)]
            })
            
            start_pos = pos + 1
        
        logger.info(f"Found {len(matches)} matches for pattern '{pattern}' in {pdf_path}")
        return matches
    
    def get_document_info(self, pdf_path: str | Path) -> Dict[str, Any]:
        """Get basic information about PDF document.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with document metadata
        """
        pdf_path = Path(pdf_path)
        
        try:
            with open(pdf_path, 'rb') as file:
                pages = list(PDFPage.get_pages(file))
                page_count = len(pages)
                
                # Get file size
                file_size = pdf_path.stat().st_size
                
                # Extract some text to estimate content
                segments = self.extract_text_segments(pdf_path)
                total_chars = sum(len(segment.text) for segment in segments)
                
                return {
                    "path": str(pdf_path),
                    "filename": pdf_path.name,
                    "file_size": file_size,
                    "page_count": page_count,
                    "character_count": total_chars,
                    "segment_count": len(segments)
                }
                
        except Exception as e:
            logger.error(f"Failed to get document info for {pdf_path}: {e}")
            raise