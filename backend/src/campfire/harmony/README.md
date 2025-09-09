# Harmony Orchestration Engine

This module provides a comprehensive orchestration engine for gpt-oss models using the Harmony format. It enables structured conversations with tool integration, multi-turn dialogue management, and proper token handling for local model inference.

## Features

- **Message Rendering**: Convert structured conversations to token IDs for model input
- **Completion Parsing**: Parse model completions back to structured messages and tool calls
- **Tool Integration**: Register and manage local tools (like the browser tool for document search)
- **Multi-turn Conversations**: Handle conversation history with automatic trimming
- **Type Safety**: Full type hints and Pydantic models for all data structures

## Quick Start

```python
from campfire.harmony import HarmonyEngine, HarmonyRole
from campfire.harmony.browser_tool import create_browser_tool_config

# Initialize the engine
engine = HarmonyEngine()

# Register the browser tool for document search
browser_tool = create_browser_tool_config()
engine.register_tool(browser_tool)

# Create messages
system_msg = engine.create_system_message("You are a helpful assistant.")
user_msg = engine.create_user_message("How do I treat a burn?")

# Add to conversation
engine.add_message(system_msg)
engine.add_message(user_msg)

# Render for model input
prefill_ids, stop_ids = engine.render_conversation()

# Use prefill_ids with your LLM provider...
# completion_tokens = your_llm.generate(prefill_ids, stop_ids)

# Parse the completion
# messages, tool_calls = engine.parse_completion(completion_tokens, prefill_ids)
```

## Core Components

### HarmonyEngine

The main orchestration class that manages conversations and tool integration.

**Key Methods:**
- `register_tool(tool_config)`: Register a tool for use in conversations
- `add_message(message)`: Add a message to the conversation history
- `render_conversation()`: Convert messages to token IDs for model input
- `parse_completion()`: Parse model output back to structured format
- `handle_multi_turn_conversation()`: Manage multi-turn dialogues with history trimming

### Message Types

All messages use the `HarmonyMessage` type with these roles:
- `HarmonyRole.SYSTEM`: System prompts and instructions
- `HarmonyRole.DEVELOPER`: Developer-specific instructions
- `HarmonyRole.USER`: User queries and input
- `HarmonyRole.ASSISTANT`: Model responses and tool calls

### Tool Integration

Tools are registered using `ToolConfig` objects that define:
- **recipient_prefix**: The tool identifier (e.g., "browser")
- **definition**: Tool methods and their parameters

Example browser tool registration:
```python
from campfire.harmony.browser_tool import create_browser_tool_config

tool_config = create_browser_tool_config()
engine.register_tool(tool_config)
```

The browser tool provides three methods:
- `search(q, k=5)`: Search the document corpus
- `open(doc_id, start, end)`: Retrieve specific text sections
- `find(doc_id, pattern, after)`: Find patterns within documents

## Advanced Usage

### Multi-turn Conversations

```python
# Handle multiple conversation turns with automatic history management
user_message = engine.create_user_message("Follow-up question")
prefill_ids, stop_ids = engine.handle_multi_turn_conversation(
    user_message, 
    max_history=10  # Keep last 10 messages
)
```

### Tool Calls and Results

```python
from campfire.harmony.types import ToolCall, ToolResult

# Create assistant message with tool calls
tool_calls = [
    ToolCall(
        recipient="browser",
        method="search", 
        args={"q": "emergency first aid", "k": 3},
        call_id="search_1"
    )
]

assistant_msg = engine.create_assistant_message(
    content="I'll search for first aid information.",
    tool_calls=tool_calls
)
```

### Conversation Management

```python
# Get conversation statistics
summary = engine.get_conversation_summary()
print(f"Messages: {summary['message_count']}")
print(f"Tool calls: {summary['tool_calls']}")
print(f"Registered tools: {summary['registered_tools']}")

# Clear conversation history
engine.clear_conversation()
```

## Error Handling

The engine provides comprehensive error handling:

- **Rendering Errors**: Wrapped in `RuntimeError` with descriptive messages
- **Parsing Errors**: Graceful handling of malformed completions
- **Tool Registration**: Validation of tool configurations
- **Conversation Limits**: Automatic history trimming to prevent memory issues

## Testing

The module includes comprehensive unit tests covering:

- Message creation and validation
- Tool registration and configuration
- Conversation rendering and parsing
- Multi-turn dialogue handling
- Error scenarios and edge cases

Run tests with:
```bash
uv run python -m pytest backend/tests/test_harmony/ -v
```

## Integration with Campfire

This Harmony engine is specifically designed for the Campfire emergency helper application:

1. **Emergency Guidance**: System prompts for emergency scenarios
2. **Document Search**: Browser tool integration for IFRC/WHO corpus
3. **Safety Critical**: Proper citation handling and safety warnings
4. **Offline Operation**: No external dependencies during inference

## Example: Emergency Guidance Flow

```python
# Set up for emergency guidance
system_prompt = """You are an emergency guidance assistant. 
Use the browser tool to search for relevant information and provide 
step-by-step guidance with proper citations."""

engine = HarmonyEngine()
engine.register_tool(create_browser_tool_config())

# Add system message
engine.add_message(engine.create_system_message(system_prompt))

# User asks for help
user_query = "Someone is choking, what should I do?"
engine.add_message(engine.create_user_message(user_query))

# Render for model
prefill_ids, stop_ids = engine.render_conversation()

# Model would generate completion with tool calls:
# 1. Search for choking information
# 2. Open relevant document sections  
# 3. Provide step-by-step guidance with citations
```

This creates a complete pipeline for emergency guidance with proper tool integration and citation handling.