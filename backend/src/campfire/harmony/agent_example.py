"""
Example usage of the agent composition system.

This script demonstrates how to use the AgentCompositionSystem
with both tool-loop and RAG fallback modes.
"""

import json
import logging
from pathlib import Path

from ..llm.vllm_provider import VLLMProvider
from ..llm.ollama_provider import OllamaProvider
from .agent import AgentCompositionSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_tool_loop_mode():
    """Demonstrate tool-loop mode with vLLM provider."""
    print("=== Tool-Loop Mode Demo (vLLM) ===")
    
    try:
        # Initialize vLLM provider
        vllm_provider = VLLMProvider(model_name="gpt-oss-20b")
        
        if not vllm_provider.is_available():
            print("vLLM provider not available, skipping tool-loop demo")
            return
        
        # Initialize agent system
        corpus_db_path = "corpus/processed/corpus.db"
        agent = AgentCompositionSystem(
            llm_provider=vllm_provider,
            corpus_db_path=corpus_db_path,
            max_tool_iterations=3
        )
        
        # Test emergency query
        query = "Someone is bleeding heavily from a cut on their arm. What should I do?"
        
        print(f"Query: {query}")
        print("Processing with tool-loop mode...")
        
        response = agent.process_query(query)
        
        print("\nResponse:")
        print(json.dumps(response.to_dict(), indent=2))
        
        # Cleanup
        agent.close()
        
    except Exception as e:
        logger.error(f"Tool-loop demo failed: {e}")


def demo_rag_fallback_mode():
    """Demonstrate RAG fallback mode with Ollama provider."""
    print("\n=== RAG Fallback Mode Demo (Ollama) ===")
    
    try:
        # Initialize Ollama provider
        ollama_provider = OllamaProvider(model_name="gpt-oss-20b")
        
        if not ollama_provider.is_available():
            print("Ollama provider not available, skipping RAG demo")
            return
        
        # Initialize agent system
        corpus_db_path = "corpus/processed/corpus.db"
        agent = AgentCompositionSystem(
            llm_provider=ollama_provider,
            corpus_db_path=corpus_db_path
        )
        
        # Test emergency query
        query = "What should I do if someone is having a panic attack?"
        
        print(f"Query: {query}")
        print("Processing with RAG fallback mode...")
        
        response = agent.process_query(query)
        
        print("\nResponse:")
        print(json.dumps(response.to_dict(), indent=2))
        
        # Cleanup
        agent.close()
        
    except Exception as e:
        logger.error(f"RAG fallback demo failed: {e}")


def demo_multi_hop_tool_calling():
    """Demonstrate multi-hop tool calling sequence."""
    print("\n=== Multi-Hop Tool Calling Demo ===")
    
    try:
        # Use mock provider for demonstration
        from ..llm.base import LLMProvider
        
        class MockProvider:
            def supports_tokens(self):
                return True
                
            def generate(self, prefill_ids, stop_token_ids, max_tokens=2048, temperature=0.1):
                # Simulate a response with tool calls
                return {
                    "completion_tokens": [1, 2, 3, 4, 5],
                    "completion_text": """
                    I need to search for information about burns first.
                    
                    <tool_call>
                    {"recipient": "browser", "method": "search", "args": {"q": "burn treatment first aid", "k": 3}}
                    </tool_call>
                    """,
                    "finish_reason": "stop",
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
                }
            
            def is_available(self):
                return True
                
            def get_model_info(self):
                return {"name": "mock", "provider": "demo"}
        
        mock_provider = MockProvider()
        
        # Initialize agent system
        corpus_db_path = "corpus/processed/corpus.db"
        agent = AgentCompositionSystem(
            llm_provider=mock_provider,
            corpus_db_path=corpus_db_path
        )
        
        # Demonstrate manual tool call sequence
        from .types import ToolCall
        
        # Step 1: Search for burn information
        search_call = ToolCall(
            recipient="browser",
            method="search",
            args={"q": "burn treatment first aid", "k": 3},
            call_id="search_1"
        )
        
        # Step 2: Open specific document
        open_call = ToolCall(
            recipient="browser",
            method="open",
            args={"doc_id": "ifrc_2020", "start": 1000, "end": 2000},
            call_id="open_1"
        )
        
        # Step 3: Find specific information
        find_call = ToolCall(
            recipient="browser",
            method="find",
            args={"doc_id": "ifrc_2020", "pattern": "cool water", "after": 1000},
            call_id="find_1"
        )
        
        tool_calls = [search_call, open_call, find_call]
        
        print("Executing multi-hop tool sequence:")
        print("1. Search for burn treatment information")
        print("2. Open specific document section")
        print("3. Find specific treatment details")
        
        results = agent._execute_tool_calls(tool_calls)
        
        print(f"\nExecuted {len(results)} tool calls:")
        for i, result in enumerate(results, 1):
            if result.error:
                print(f"  {i}. Error: {result.error}")
            else:
                print(f"  {i}. Success: {type(result.result).__name__}")
        
        # Cleanup
        agent.close()
        
    except Exception as e:
        logger.error(f"Multi-hop demo failed: {e}")


def demo_error_handling():
    """Demonstrate error handling capabilities."""
    print("\n=== Error Handling Demo ===")
    
    try:
        # Create a provider that will fail
        class FailingProvider:
            def supports_tokens(self):
                return True
                
            def generate(self, prefill_ids, stop_token_ids, max_tokens=2048, temperature=0.1):
                raise Exception("Simulated model failure")
            
            def is_available(self):
                return True
                
            def get_model_info(self):
                return {"name": "failing", "provider": "demo"}
        
        failing_provider = FailingProvider()
        
        # Initialize agent system
        corpus_db_path = "corpus/processed/corpus.db"
        agent = AgentCompositionSystem(
            llm_provider=failing_provider,
            corpus_db_path=corpus_db_path
        )
        
        # Test with failing provider
        query = "What should I do in an emergency?"
        
        print(f"Query: {query}")
        print("Processing with failing provider...")
        
        response = agent.process_query(query)
        
        print("\nError Response:")
        print(json.dumps(response.to_dict(), indent=2))
        
        # Cleanup
        agent.close()
        
    except Exception as e:
        logger.error(f"Error handling demo failed: {e}")


def demo_structured_output_parsing():
    """Demonstrate structured output parsing."""
    print("\n=== Structured Output Parsing Demo ===")
    
    # Test JSON extraction
    from .agent import AgentCompositionSystem
    
    # Create dummy agent for testing parsing methods
    class DummyProvider:
        def supports_tokens(self):
            return False
        def is_available(self):
            return True
        def get_model_info(self):
            return {}
    
    agent = AgentCompositionSystem(DummyProvider(), "/tmp/dummy.db")
    
    # Test various response formats
    test_responses = [
        # JSON in code block
        '''
        Here's the emergency response:
        ```json
        {
          "checklist": [
            {
              "title": "Assess the situation",
              "action": "Check if the area is safe before approaching",
              "source": {"doc_id": "ifrc_2020", "loc": [100, 200]},
              "caution": "Do not put yourself in danger"
            }
          ],
          "meta": {
            "disclaimer": "Not medical advice",
            "when_to_call_emergency": "If person is unconscious"
          }
        }
        ```
        ''',
        
        # Inline JSON
        '''
        Response: {"checklist": [{"title": "Call for help", "action": "Dial emergency services"}], "meta": {"disclaimer": "Emergency guidance only"}}
        ''',
        
        # Structured text (fallback)
        '''
        Step 1: Check consciousness
        Tap shoulders and shout "Are you okay?"
        
        Step 2: Call emergency services
        If no response, call 911 immediately
        
        Step 3: Check breathing
        Look for chest movement for 10 seconds
        '''
    ]
    
    for i, response_text in enumerate(test_responses, 1):
        print(f"\nTest {i}: Parsing response format {i}")
        try:
            parsed_response = agent._parse_text_response(response_text)
            print(f"  Parsed {len(parsed_response.checklist)} steps")
            print(f"  First step: {parsed_response.checklist[0].title}")
        except Exception as e:
            print(f"  Parsing failed: {e}")


if __name__ == "__main__":
    print("Campfire Agent Composition System Demo")
    print("=" * 50)
    
    # Check if corpus database exists
    corpus_db_path = Path("corpus/processed/corpus.db")
    if not corpus_db_path.exists():
        print(f"Warning: Corpus database not found at {corpus_db_path}")
        print("Some demos may not work without the corpus database.")
        print()
    
    # Run demos
    demo_structured_output_parsing()
    demo_multi_hop_tool_calling()
    demo_error_handling()
    
    # Only run provider demos if corpus exists
    if corpus_db_path.exists():
        demo_tool_loop_mode()
        demo_rag_fallback_mode()
    else:
        print("\nSkipping provider demos - corpus database not available")
    
    print("\nDemo completed!")