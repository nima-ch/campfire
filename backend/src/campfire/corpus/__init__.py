"""
Campfire document corpus management system.

This module provides functionality for ingesting, indexing, and searching
local documents for the emergency helper application.
"""

from .database import CorpusDatabase
from .extractor import PDFExtractor
from .chunker import TextChunker
from .ingestion import DocumentIngester

__all__ = [
    "CorpusDatabase",
    "PDFExtractor", 
    "TextChunker",
    "DocumentIngester",
]