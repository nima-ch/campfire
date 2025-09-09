"""
Command-line interface for corpus management.
"""

import typer
from pathlib import Path
from typing import Optional
import logging

from .database import CorpusDatabase
from .extractor import PDFExtractor
from .chunker import TextChunker
from .ingestion import DocumentIngester

app = typer.Typer(help="Campfire corpus management CLI")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.command()
def init_db(
    db_path: str = typer.Option("corpus.db", help="Database file path"),
):
    """Initialize corpus database."""
    db = CorpusDatabase(db_path)
    db.initialize_schema()
    typer.echo(f"Initialized database at {db_path}")


@app.command()
def ingest(
    pdf_path: str = typer.Argument(..., help="Path to PDF file or directory"),
    db_path: str = typer.Option("corpus.db", help="Database file path"),
    doc_id: Optional[str] = typer.Option(None, help="Document ID (auto-generated if not provided)"),
    title: Optional[str] = typer.Option(None, help="Document title (filename if not provided)"),
    chunk_size: int = typer.Option(1000, help="Chunk size in characters"),
    overlap_size: int = typer.Option(200, help="Overlap size in characters"),
):
    """Ingest PDF document(s) into corpus."""
    pdf_path = Path(pdf_path)
    
    # Initialize components
    db = CorpusDatabase(db_path)
    db.initialize_schema()
    
    extractor = PDFExtractor()
    chunker = TextChunker(chunk_size=chunk_size, overlap_size=overlap_size)
    ingester = DocumentIngester(db, extractor, chunker)
    
    try:
        if pdf_path.is_file():
            # Ingest single file
            result = ingester.ingest_pdf(pdf_path, doc_id=doc_id, title=title)
            typer.echo(f"Ingestion result: {result['status']}")
            if result["status"] == "success":
                typer.echo(f"Document ID: {result['doc_id']}")
                typer.echo(f"Chunks created: {result['chunking']['chunks']}")
        elif pdf_path.is_dir():
            # Ingest directory
            results = ingester.ingest_directory(pdf_path)
            successful = len([r for r in results if r["status"] == "success"])
            typer.echo(f"Ingested {successful}/{len(results)} documents successfully")
        else:
            typer.echo(f"Path not found: {pdf_path}", err=True)
            raise typer.Exit(1)
            
    except Exception as e:
        typer.echo(f"Ingestion failed: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    db_path: str = typer.Option("corpus.db", help="Database file path"),
    limit: int = typer.Option(5, help="Maximum number of results"),
):
    """Search corpus for text."""
    db = CorpusDatabase(db_path)
    
    try:
        results = db.search(query, limit=limit)
        
        if not results:
            typer.echo("No results found.")
            return
        
        typer.echo(f"Found {len(results)} results:")
        typer.echo()
        
        for i, result in enumerate(results, 1):
            typer.echo(f"{i}. Document: {result['doc_title']}")
            typer.echo(f"   Page: {result['page_number']}")
            typer.echo(f"   Offset: {result['start_offset']}-{result['end_offset']}")
            typer.echo(f"   Text: {result['text'][:200]}...")
            typer.echo()
            
    except Exception as e:
        typer.echo(f"Search failed: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def list_docs(
    db_path: str = typer.Option("corpus.db", help="Database file path"),
):
    """List all documents in corpus."""
    db = CorpusDatabase(db_path)
    
    try:
        documents = db.list_documents()
        
        if not documents:
            typer.echo("No documents found.")
            return
        
        typer.echo(f"Found {len(documents)} documents:")
        typer.echo()
        
        for doc in documents:
            typer.echo(f"ID: {doc['doc_id']}")
            typer.echo(f"Title: {doc['title']}")
            typer.echo(f"Path: {doc['path']}")
            typer.echo(f"Created: {doc['created_at']}")
            typer.echo()
            
    except Exception as e:
        typer.echo(f"Failed to list documents: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def stats(
    db_path: str = typer.Option("corpus.db", help="Database file path"),
):
    """Show corpus statistics."""
    db = CorpusDatabase(db_path)
    
    try:
        stats = db.get_stats()
        
        typer.echo("Corpus Statistics:")
        typer.echo(f"Documents: {stats['documents']}")
        typer.echo(f"Chunks: {stats['chunks']}")
        
        if stats['documents'] > 0:
            avg_chunks = stats['chunks'] / stats['documents']
            typer.echo(f"Average chunks per document: {avg_chunks:.1f}")
            
    except Exception as e:
        typer.echo(f"Failed to get statistics: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def validate(
    doc_id: str = typer.Argument(..., help="Document ID to validate"),
    db_path: str = typer.Option("corpus.db", help="Database file path"),
):
    """Validate document ingestion."""
    db = CorpusDatabase(db_path)
    extractor = PDFExtractor()
    chunker = TextChunker()
    ingester = DocumentIngester(db, extractor, chunker)
    
    try:
        validation = ingester.validate_ingestion(doc_id)
        
        typer.echo(f"Validation for document '{doc_id}':")
        typer.echo(f"Valid: {validation['valid']}")
        
        if not validation['valid']:
            if 'error' in validation:
                typer.echo(f"Error: {validation['error']}")
            if 'issues' in validation:
                typer.echo("Issues:")
                for issue in validation['issues']:
                    typer.echo(f"  - {issue}")
        else:
            typer.echo(f"Chunks: {validation['chunk_count']}")
            typer.echo(f"Search functional: {validation['search_functional']}")
            
    except Exception as e:
        typer.echo(f"Validation failed: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def delete(
    doc_id: str = typer.Argument(..., help="Document ID to delete"),
    db_path: str = typer.Option("corpus.db", help="Database file path"),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
):
    """Delete document from corpus."""
    if not confirm:
        confirmed = typer.confirm(f"Are you sure you want to delete document '{doc_id}'?")
        if not confirmed:
            typer.echo("Cancelled.")
            return
    
    db = CorpusDatabase(db_path)
    
    try:
        result = db.delete_document(doc_id)
        
        if result:
            typer.echo(f"Deleted document '{doc_id}'")
        else:
            typer.echo(f"Document '{doc_id}' not found")
            
    except Exception as e:
        typer.echo(f"Deletion failed: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    app()