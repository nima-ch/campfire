"""
Example usage of the LocalBrowserTool for document search and retrieval.

This example demonstrates how the browser tool would be used in the context
of the Harmony orchestration system for emergency guidance queries.
"""

import tempfile
import os
from pathlib import Path

from .browser import LocalBrowserTool
from ..corpus.database import CorpusDatabase


def create_example_corpus() -> str:
    """Create an example corpus database for demonstration.
    
    Returns:
        Path to the temporary database file
    """
    # Create temporary database
    temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = temp_file.name
    temp_file.close()
    
    # Initialize database
    db = CorpusDatabase(db_path)
    db.initialize_schema()
    
    # Add example emergency guidance documents
    db.add_document("ifrc_burns", "IFRC First Aid - Burns", "/corpus/ifrc_burns.pdf")
    db.add_document("who_pfa", "WHO Psychological First Aid", "/corpus/who_pfa.pdf")
    
    # Add realistic emergency guidance content
    burn_chunks = [
        ("Burns are injuries caused by heat, chemicals, electricity, or radiation. "
         "The severity depends on temperature, duration of contact, and area affected.", 0, 120, 1),
        ("For minor burns: Immediately cool the burn with cold running water for at least 10 minutes. "
         "This helps reduce pain and prevent further tissue damage.", 121, 250, 1),
        ("Remove jewelry, watches, and tight clothing before swelling begins. "
         "Do not remove clothing that is stuck to the burn.", 251, 360, 2),
        ("Cover the burn with a sterile, non-adhesive bandage or clean cloth. "
         "Do not apply ice, butter, oils, or other home remedies.", 361, 480, 2),
        ("Seek immediate medical attention for burns larger than your palm, "
         "burns on face/hands/feet/genitals, or signs of infection.", 481, 600, 3),
    ]
    
    for text, start, end, page in burn_chunks:
        db.add_chunk("ifrc_burns", text, start, end, page)
    
    # Add psychological first aid content
    pfa_chunks = [
        ("Psychological First Aid (PFA) is a humane, supportive response to people "
         "suffering from crisis or disaster situations.", 0, 110, 1),
        ("The core principles of PFA are: Look, Listen, and Link. "
         "First, look for people who may need support.", 111, 200, 1),
        ("Listen actively to understand their needs and concerns. "
         "Provide practical support and information.", 201, 290, 2),
        ("Link people with social supports and services that may help them cope. "
         "Follow up when possible.", 291, 380, 2),
    ]
    
    for text, start, end, page in pfa_chunks:
        db.add_chunk("who_pfa", text, start, end, page)
    
    db.close()
    return db_path


def demonstrate_browser_tool():
    """Demonstrate browser tool functionality with example queries."""
    print("=== LocalBrowserTool Demonstration ===\n")
    
    # Create example corpus
    db_path = create_example_corpus()
    browser = LocalBrowserTool(db_path)
    
    try:
        # Example 1: Search for burn treatment
        print("1. Searching for burn treatment information:")
        search_result = browser.search("burn treatment cold water", k=3)
        
        print(f"   Status: {search_result['status']}")
        print(f"   Query: '{search_result['query']}'")
        print(f"   Results found: {search_result['total_results']}\n")
        
        for i, result in enumerate(search_result['results'], 1):
            print(f"   Result {i}:")
            print(f"     Document: {result['doc_title']}")
            print(f"     Snippet: {result['snippet'][:100]}...")
            print(f"     Location: {result['location']['start_offset']}-{result['location']['end_offset']}")
            print()
        
        # Example 2: Open specific content
        if search_result['results']:
            first_result = search_result['results'][0]
            print("2. Opening detailed content from first result:")
            
            open_result = browser.open(
                first_result['doc_id'],
                first_result['location']['start_offset'],
                first_result['location']['end_offset']
            )
            
            print(f"   Status: {open_result['status']}")
            print(f"   Document: {open_result['doc_title']}")
            print(f"   Text: {open_result['text']}")
            print()
        
        # Example 3: Find specific patterns
        print("3. Finding specific guidance patterns:")
        find_result = browser.find("ifrc_burns", "medical attention", 0)
        
        print(f"   Status: {find_result['status']}")
        print(f"   Pattern: '{find_result['pattern']}'")
        print(f"   Matches found: {find_result['total_matches']}\n")
        
        for i, match in enumerate(find_result['matches'], 1):
            print(f"   Match {i}:")
            print(f"     Text: {match['text']}")
            print(f"     Context: {match['context'][:80]}...")
            print(f"     Location: {match['location']['start_offset']}-{match['location']['end_offset']}")
            print()
        
        # Example 4: Multi-step workflow
        print("4. Multi-step information gathering workflow:")
        
        # Step 1: Search for psychological support
        pfa_search = browser.search("psychological support crisis")
        print(f"   Step 1 - Search results: {pfa_search['total_results']} found")
        
        if pfa_search['results']:
            # Step 2: Open the content
            pfa_result = pfa_search['results'][0]
            pfa_content = browser.open(
                pfa_result['doc_id'],
                pfa_result['location']['start_offset'],
                pfa_result['location']['end_offset']
            )
            print(f"   Step 2 - Opened content: {len(pfa_content['text'])} characters")
            
            # Step 3: Find specific techniques
            techniques = browser.find(pfa_result['doc_id'], "Listen", 0)
            print(f"   Step 3 - Found techniques: {techniques['total_matches']} matches")
        
        print("\n=== Demonstration Complete ===")
        
    finally:
        # Cleanup
        browser.close()
        os.unlink(db_path)


if __name__ == "__main__":
    demonstrate_browser_tool()