"""
Command-line interface for Campfire emergency helper.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.logging import RichHandler

from . import __version__

app = typer.Typer(
    name="campfire",
    help="Campfire Emergency Helper - Offline emergency guidance system",
    add_completion=False
)
console = Console()


def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    debug: bool = typer.Option(False, help="Enable debug mode"),
    corpus_db: Optional[str] = typer.Option(None, help="Path to corpus database"),
    policy_file: Optional[str] = typer.Option(None, help="Path to policy file"),
    llm_provider: str = typer.Option("ollama", help="LLM provider (ollama, vllm, lmstudio)"),
):
    """Start the Campfire API server."""
    setup_logging(debug)
    
    # Set environment variables
    if corpus_db:
        os.environ["CAMPFIRE_CORPUS_DB"] = corpus_db
    if policy_file:
        os.environ["CAMPFIRE_POLICY_PATH"] = policy_file
    if debug:
        os.environ["CAMPFIRE_DEBUG"] = "1"
    
    os.environ["CAMPFIRE_LLM_PROVIDER"] = llm_provider
    
    console.print(f"🔥 Starting Campfire Emergency Helper v{__version__}")
    console.print(f"📡 Server: http://{host}:{port}")
    console.print(f"🤖 LLM Provider: {llm_provider}")
    console.print(f"🔒 Offline Mode: Enabled")
    
    if debug:
        console.print(f"📚 API Docs: http://{host}:{port}/docs")
    
    try:
        uvicorn.run(
            "campfire.api.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="debug" if debug else "info",
            access_log=debug
        )
    except KeyboardInterrupt:
        console.print("\n👋 Shutting down Campfire server...")
    except Exception as e:
        console.print(f"❌ Server error: {e}", style="red")
        sys.exit(1)


@app.command()
def check(
    corpus_db: Optional[str] = typer.Option(None, help="Path to corpus database"),
    policy_file: Optional[str] = typer.Option(None, help="Path to policy file"),
):
    """Check system configuration and dependencies."""
    setup_logging()
    
    console.print("🔍 Checking Campfire configuration...")
    
    # Check corpus database
    corpus_path = corpus_db or os.getenv("CAMPFIRE_CORPUS_DB", "corpus/processed/corpus.db")
    if Path(corpus_path).exists():
        console.print(f"✅ Corpus database found: {corpus_path}")
        
        # Try to connect and get document count
        try:
            from .corpus.database import CorpusDatabase
            db = CorpusDatabase(corpus_path)
            docs = db.list_documents()
            console.print(f"📚 Documents in corpus: {len(docs)}")
            db.close()
        except Exception as e:
            console.print(f"⚠️  Corpus database error: {e}", style="yellow")
    else:
        console.print(f"❌ Corpus database not found: {corpus_path}", style="red")
    
    # Check policy file
    policy_path = policy_file or os.getenv("CAMPFIRE_POLICY_PATH", "policy.md")
    if Path(policy_path).exists():
        console.print(f"✅ Policy file found: {policy_path}")
    else:
        console.print(f"⚠️  Policy file not found: {policy_path} (will use defaults)", style="yellow")
    
    # Check LLM providers
    console.print("🤖 Checking LLM providers...")
    
    try:
        from .llm.factory import get_available_providers
        providers = get_available_providers()
        
        for provider_name, available in providers.items():
            status = "✅" if available else "❌"
            console.print(f"{status} {provider_name}: {'Available' if available else 'Not available'}")
    except Exception as e:
        console.print(f"❌ Error checking LLM providers: {e}", style="red")
    
    # Check dependencies
    console.print("📦 Checking dependencies...")
    
    required_packages = [
        "fastapi", "uvicorn", "pydantic", "sqlalchemy", 
        "openai-harmony", "pdfminer.six", "rich", "typer"
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            console.print(f"✅ {package}")
        except ImportError:
            console.print(f"❌ {package} (missing)", style="red")
    
    console.print("\n🔥 Configuration check complete!")


@app.command()
def version():
    """Show version information."""
    console.print(f"Campfire Emergency Helper v{__version__}")


@app.command()
def ingest(
    input_dir: str = typer.Argument(..., help="Directory containing PDF files to ingest"),
    output_db: str = typer.Option("corpus/processed/corpus.db", help="Output database path"),
    force: bool = typer.Option(False, help="Overwrite existing database"),
):
    """Ingest PDF documents into the corpus database."""
    setup_logging()
    
    input_path = Path(input_dir)
    output_path = Path(output_db)
    
    if not input_path.exists():
        console.print(f"❌ Input directory not found: {input_path}", style="red")
        sys.exit(1)
    
    if output_path.exists() and not force:
        console.print(f"❌ Database already exists: {output_path}", style="red")
        console.print("Use --force to overwrite")
        sys.exit(1)
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    console.print(f"📚 Ingesting documents from: {input_path}")
    console.print(f"💾 Output database: {output_path}")
    
    try:
        from .corpus.ingestion import DocumentIngester
        
        ingester = DocumentIngester(str(output_path))
        
        # Find PDF files
        pdf_files = list(input_path.glob("*.pdf"))
        if not pdf_files:
            console.print(f"❌ No PDF files found in: {input_path}", style="red")
            sys.exit(1)
        
        console.print(f"📄 Found {len(pdf_files)} PDF files")
        
        # Ingest each file
        for pdf_file in pdf_files:
            console.print(f"Processing: {pdf_file.name}")
            try:
                ingester.ingest_document(str(pdf_file))
                console.print(f"✅ Ingested: {pdf_file.name}")
            except Exception as e:
                console.print(f"❌ Failed to ingest {pdf_file.name}: {e}", style="red")
        
        console.print("🔥 Document ingestion complete!")
        
    except Exception as e:
        console.print(f"❌ Ingestion error: {e}", style="red")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()