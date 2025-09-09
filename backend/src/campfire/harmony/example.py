"""Example usage of the Harmony orchestration engine."""

import logging
from typing import List

from .browser_tool import create_browser_tool_config
from .engine import HarmonyEngine
from .types import HarmonyMessage, HarmonyRole, ToolCall

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_emergency_system_prompt() -> str:
    """Create the system prompt for emergency guidance."""
    return """You are an emergency guidance assistant that helps users with household and community emergencies. 

You have access to a local document corpus containing IFRC First Aid Guidelines (2020) and WHO Psychological First Aid (2011). Use the browser tool to search for relevant information and provide step-by-step guidance with proper citations.

Always:
1. Search for relevant information using the browser tool
2. Provide actionable steps in a checklist format
3. Include proper citations for each step
4. Add appropriate safety warnings
5. Remind users this is not medical advice and to call emergency services for serious situations

Use the browser tool methods:
- search(q, k=5): Search the document corpus
- open(doc_id, start, end): Retrieve specific text sections
- find(doc_id, pattern, after): Find patterns within documents"""


def demonstrate_harmony_engine():
    """Demonstrate the Harmony engine with browser tool integration."""
    logger.info("Initializing Harmony engine...")
    
    # Create and configure the engine
    engine = HarmonyEngine()
    
    # Register the browser tool
    browser_tool = create_browser_tool_config()
    engine.register_tool(browser_tool)
    
    logger.info("Registered browser tool with methods: %s", 
                [method["name"] for method in browser_tool.definition.methods])
    
    # Create a conversation
    system_message = engine.create_system_message(create_emergency_system_prompt())
    user_message = engine.create_user_message("How do I treat a minor burn?")
    
    # Add messages to conversation
    engine.add_message(system_message)
    engine.add_message(user_message)
    
    logger.info("Created conversation with %d messages", len(engine.conversation_history))
    
    # Render the conversation for model input
    try:
        prefill_ids, stop_ids = engine.render_conversation()
        logger.info("Successfully rendered conversation:")
        logger.info("  - Prefill tokens: %d", len(prefill_ids))
        logger.info("  - Stop tokens: %d", len(stop_ids))
        logger.info("  - First few prefill tokens: %s", prefill_ids[:10])
        logger.info("  - Stop token IDs: %s", stop_ids)
        
        # Simulate a completion with tool calls
        # In a real scenario, these would come from the LLM
        simulated_completion_tokens = [1234, 5678, 9012]  # Placeholder tokens
        
        # For demonstration, let's create a mock assistant response with tool calls
        assistant_message = engine.create_assistant_message(
            content="I'll search for information about treating minor burns.",
            tool_calls=[
                ToolCall(
                    recipient="browser",
                    method="search",
                    args={"q": "minor burn treatment first aid", "k": 3},
                    call_id="search_1"
                )
            ]
        )
        
        engine.add_message(assistant_message)
        logger.info("Added assistant message with tool call")
        
        # Get conversation summary
        summary = engine.get_conversation_summary()
        logger.info("Conversation summary: %s", summary)
        
        return True
        
    except Exception as e:
        logger.error("Failed to render conversation: %s", e)
        return False


def demonstrate_multi_turn_conversation():
    """Demonstrate multi-turn conversation handling."""
    logger.info("Demonstrating multi-turn conversation...")
    
    engine = HarmonyEngine()
    browser_tool = create_browser_tool_config()
    engine.register_tool(browser_tool)
    
    # Add initial system message
    system_msg = engine.create_system_message(create_emergency_system_prompt())
    engine.add_message(system_msg)
    
    # Simulate multiple turns
    user_queries = [
        "What should I do if someone is choking?",
        "How do I perform CPR?",
        "What are the signs of a heart attack?"
    ]
    
    for i, query in enumerate(user_queries):
        logger.info("Turn %d: %s", i + 1, query)
        
        user_msg = engine.create_user_message(query)
        
        try:
            # Handle multi-turn conversation
            prefill_ids, stop_ids = engine.handle_multi_turn_conversation(
                user_msg, max_history=8
            )
            
            logger.info("  - Rendered %d prefill tokens, %d stop tokens", 
                       len(prefill_ids), len(stop_ids))
            logger.info("  - Conversation has %d messages", 
                       len(engine.conversation_history))
            
        except Exception as e:
            logger.error("  - Failed to handle turn: %s", e)
            return False
    
    return True


if __name__ == "__main__":
    print("=== Harmony Engine Demonstration ===")
    
    print("\n1. Basic engine functionality:")
    success1 = demonstrate_harmony_engine()
    print(f"   Result: {'✓ Success' if success1 else '✗ Failed'}")
    
    print("\n2. Multi-turn conversation:")
    success2 = demonstrate_multi_turn_conversation()
    print(f"   Result: {'✓ Success' if success2 else '✗ Failed'}")
    
    if success1 and success2:
        print("\n🎉 All demonstrations completed successfully!")
        print("The Harmony orchestration engine is ready for integration.")
    else:
        print("\n❌ Some demonstrations failed. Check the logs above.")