#!/usr/bin/env python3
"""
Demo script for the Campfire corpus system.

This script demonstrates the basic functionality of the document corpus
system including PDF ingestion, text chunking, and search capabilities.
"""

import sys
import tempfile
from pathlib import Path

# Add the backend source to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from campfire.corpus import CorpusDatabase, PDFExtractor, TextChunker, DocumentIngester


def create_sample_text_file():
    """Create a sample text file that simulates PDF content."""
    content = """
Emergency Response Procedures

Chapter 1: Fire Safety
In case of fire emergency, follow these steps:
1. Remain calm and assess the situation quickly
2. Alert others in the immediate area
3. Call emergency services immediately (911)
4. Evacuate the building if safe to do so
5. Do not use elevators during evacuation
6. Meet at the designated assembly point

Chapter 2: First Aid Guidelines

For minor burns:
1. Cool the burn with running water for 10-20 minutes
2. Remove any jewelry or tight clothing near the burn area
3. Cover with a clean, sterile bandage
4. Apply a thin layer of antibiotic ointment if available
5. Seek medical attention if the burn is larger than 3 inches

For cuts and wounds:
1. Apply direct pressure to control bleeding
2. Clean the wound with clean water if possible
3. Apply antibiotic ointment to prevent infection
4. Cover with a sterile bandage
5. Change the bandage daily and keep the wound clean

Chapter 3: Emergency Contacts
- Fire Department: 911
- Police: 911
- Poison Control: 1-800-222-1222
- Local Hospital: (555) 123-4567

Remember: This is not medical advice. Always seek professional help for serious injuries.
"""
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        return Path(f.name)


def demo_corpus_system():
    """Demonstrate the corpus system functionality."""
    print("🔥 Campfire Corpus System Demo")
    print("=" * 50)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Initialize components
        print("\n1. Initializing corpus system...")
        db = CorpusDatabase(db_path)
        db.initialize_schema()
        
        extractor = PDFExtractor()
        chunker = TextChunker(chunk_size=300, overlap_size=50)
        ingester = DocumentIngester(db, extractor, chunker)
        
        print("✅ Database and components initialized")
        
        # Create sample content (simulating PDF extraction)
        print("\n2. Creating sample emergency guide content...")
        sample_file = create_sample_text_file()
        
        # Simulate PDF ingestion by manually creating segments
        from campfire.corpus.extractor import TextSegment
        
        with open(sample_file, 'r') as f:
            content = f.read()
        
        # Mock the PDF extraction process
        segments = [TextSegment(content, 1, 0, len(content))]
        
        # Add document to database
        doc_id = "emergency_guide_2024"
        title = "Emergency Response Guide 2024"
        
        db.add_document(doc_id, title, str(sample_file))
        print(f"✅ Added document: {title}")
        
        # Chunk the content
        print("\n3. Chunking document content...")
        chunks = chunker.chunk_with_segments(segments, doc_id)
        chunks = chunker.merge_small_chunks(chunks)
        
        # Add chunks to database
        chunk_ids = []
        for chunk in chunks:
            chunk_id = db.add_chunk(
                doc_id=doc_id,
                text=chunk.text,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                page_number=1
            )
            chunk_ids.append(chunk_id)
        
        print(f"✅ Created {len(chunks)} text chunks")
        
        # Display corpus statistics
        print("\n4. Corpus Statistics:")
        stats = db.get_stats()
        print(f"   Documents: {stats['documents']}")
        print(f"   Text chunks: {stats['chunks']}")
        
        # Demonstrate search functionality
        print("\n5. Testing search functionality...")
        
        search_queries = [
            "fire emergency",
            "first aid",
            "burns",
            "bleeding",
            "emergency contacts"
        ]
        
        for query in search_queries:
            print(f"\n🔍 Searching for: '{query}'")
            results = db.search(query, limit=2)
            
            if results:
                for i, result in enumerate(results, 1):
                    print(f"   Result {i}:")
                    print(f"   📄 Document: {result['doc_title']}")
                    print(f"   📍 Page: {result['page_number']}")
                    print(f"   📝 Text: {result['text'][:150]}...")
                    print()
            else:
                print("   No results found")
        
        # Test specific chunk retrieval
        print("\n6. Testing chunk retrieval...")
        chunks = db.get_document_chunks(doc_id)
        print(f"   Retrieved {len(chunks)} chunks for document")
        
        if chunks:
            first_chunk = chunks[0]
            print(f"   First chunk preview: {first_chunk['text'][:100]}...")
        
        # Validate ingestion
        print("\n7. Validating document ingestion...")
        validation = ingester.validate_ingestion(doc_id)
        
        if validation["valid"]:
            print("✅ Document validation passed")
            print(f"   Chunks: {validation['chunk_count']}")
            print(f"   Search functional: {validation['search_functional']}")
        else:
            print("❌ Document validation failed")
            for issue in validation.get("issues", []):
                print(f"   Issue: {issue}")
        
        print("\n8. Demo completed successfully! 🎉")
        print("\nThe corpus system can:")
        print("• Extract text from PDF documents")
        print("• Chunk text with configurable overlap")
        print("• Store documents in SQLite with FTS5 search")
        print("• Perform fast full-text search")
        print("• Retrieve specific text segments with metadata")
        print("• Validate ingestion integrity")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        try:
            db.close()
            Path(db_path).unlink(missing_ok=True)
            sample_file.unlink(missing_ok=True)
        except:
            pass


if __name__ == "__main__":
    demo_corpus_system()