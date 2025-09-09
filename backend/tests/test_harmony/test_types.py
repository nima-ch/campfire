"""Tests for Harmony type definitions."""

import pytest
from pydantic import ValidationError

from campfire.harmony.types import (
    HarmonyMessage,
    HarmonyRole,
    ToolCall,
    ToolConfig,
    ToolDefinition,
    ToolResult
)


class TestHarmonyTypes:
    """Test cases for Harmony type definitions."""
    
    def test_harmony_role_enum(self):
        """Test HarmonyRole enum values."""
        assert HarmonyRole.SYSTEM == "system"
        assert HarmonyRole.DEVELOPER == "developer"
        assert HarmonyRole.USER == "user"
        assert HarmonyRole.ASSISTANT == "assistant"
    
    def test_tool_call_creation(self):
        """Test ToolCall model creation."""
        tool_call = ToolCall(
            recipient="browser",
            method="search",
            args={"q": "test query", "k": 5},
            call_id="call_123"
        )
        
        assert tool_call.recipient == "browser"
        assert tool_call.method == "search"
        assert tool_call.args == {"q": "test query", "k": 5}
        assert tool_call.call_id == "call_123"
    
    def test_tool_call_without_call_id(self):
        """Test ToolCall creation without call_id."""
        tool_call = ToolCall(
            recipient="browser",
            method="search",
            args={"q": "test"}
        )
        
        assert tool_call.call_id is None
    
    def test_tool_result_creation(self):
        """Test ToolResult model creation."""
        tool_result = ToolResult(
            call_id="call_123",
            result={"documents": ["doc1", "doc2"]},
            error=None
        )
        
        assert tool_result.call_id == "call_123"
        assert tool_result.result == {"documents": ["doc1", "doc2"]}
        assert tool_result.error is None
    
    def test_tool_result_with_error(self):
        """Test ToolResult creation with error."""
        tool_result = ToolResult(
            call_id="call_123",
            result=None,
            error="Search failed"
        )
        
        assert tool_result.call_id == "call_123"
        assert tool_result.result is None
        assert tool_result.error == "Search failed"
    
    def test_harmony_message_basic(self):
        """Test basic HarmonyMessage creation."""
        message = HarmonyMessage(
            role=HarmonyRole.USER,
            content="Hello, how can I help with emergencies?"
        )
        
        assert message.role == HarmonyRole.USER
        assert message.content == "Hello, how can I help with emergencies?"
        assert message.tool_calls is None
        assert message.tool_results is None
    
    def test_harmony_message_with_tool_calls(self):
        """Test HarmonyMessage with tool calls."""
        tool_calls = [
            ToolCall(
                recipient="browser",
                method="search",
                args={"q": "first aid"},
                call_id="call_1"
            ),
            ToolCall(
                recipient="browser", 
                method="open",
                args={"doc_id": "ifrc_2020", "start": 100, "end": 200},
                call_id="call_2"
            )
        ]
        
        message = HarmonyMessage(
            role=HarmonyRole.ASSISTANT,
            content="I'll search for first aid information.",
            tool_calls=tool_calls
        )
        
        assert message.role == HarmonyRole.ASSISTANT
        assert len(message.tool_calls) == 2
        assert message.tool_calls[0].method == "search"
        assert message.tool_calls[1].method == "open"
    
    def test_harmony_message_with_tool_results(self):
        """Test HarmonyMessage with tool results."""
        tool_results = [
            ToolResult(
                call_id="call_1",
                result={"found": 5, "documents": ["doc1", "doc2"]}
            ),
            ToolResult(
                call_id="call_2",
                result="First aid text content here...",
                error=None
            )
        ]
        
        message = HarmonyMessage(
            role=HarmonyRole.ASSISTANT,
            content="Based on the search results...",
            tool_results=tool_results
        )
        
        assert message.role == HarmonyRole.ASSISTANT
        assert len(message.tool_results) == 2
        assert message.tool_results[0].call_id == "call_1"
        assert message.tool_results[1].call_id == "call_2"
    
    def test_tool_definition_creation(self):
        """Test ToolDefinition model creation."""
        tool_def = ToolDefinition(
            name="browser",
            methods=[
                {
                    "name": "search",
                    "args": {"q": "string", "k": "integer"}
                },
                {
                    "name": "open", 
                    "args": {"doc_id": "string", "start": "integer", "end": "integer"}
                }
            ]
        )
        
        assert tool_def.name == "browser"
        assert len(tool_def.methods) == 2
        assert tool_def.methods[0]["name"] == "search"
        assert tool_def.methods[1]["name"] == "open"
    
    def test_tool_config_creation(self):
        """Test ToolConfig model creation."""
        tool_def = ToolDefinition(
            name="browser",
            methods=[{"name": "search", "args": {"q": "string"}}]
        )
        
        tool_config = ToolConfig(
            recipient_prefix="browser",
            definition=tool_def
        )
        
        assert tool_config.recipient_prefix == "browser"
        assert tool_config.definition == tool_def
        assert tool_config.definition.name == "browser"
    
    def test_harmony_message_validation_error(self):
        """Test HarmonyMessage validation errors."""
        with pytest.raises(ValidationError):
            # Missing required content field
            HarmonyMessage(role=HarmonyRole.USER)
        
        with pytest.raises(ValidationError):
            # Invalid role
            HarmonyMessage(role="invalid_role", content="test")
    
    def test_tool_call_validation_error(self):
        """Test ToolCall validation errors."""
        with pytest.raises(ValidationError):
            # Missing required fields
            ToolCall(recipient="browser")
        
        with pytest.raises(ValidationError):
            # Missing method
            ToolCall(recipient="browser", args={"q": "test"})
    
    def test_tool_result_validation_error(self):
        """Test ToolResult validation errors."""
        with pytest.raises(ValidationError):
            # Missing required call_id
            ToolResult(result="test result")
    
    def test_message_serialization(self):
        """Test message serialization to dict."""
        tool_call = ToolCall(
            recipient="browser",
            method="search", 
            args={"q": "emergency"},
            call_id="call_1"
        )
        
        message = HarmonyMessage(
            role=HarmonyRole.ASSISTANT,
            content="Searching for emergency information...",
            tool_calls=[tool_call]
        )
        
        # Test that the message can be serialized
        message_dict = message.model_dump()
        
        assert message_dict["role"] == "assistant"
        assert message_dict["content"] == "Searching for emergency information..."
        assert len(message_dict["tool_calls"]) == 1
        assert message_dict["tool_calls"][0]["recipient"] == "browser"
    
    def test_message_deserialization(self):
        """Test message deserialization from dict."""
        message_data = {
            "role": "user",
            "content": "How do I treat a burn?",
            "tool_calls": None,
            "tool_results": None
        }
        
        message = HarmonyMessage(**message_data)
        
        assert message.role == HarmonyRole.USER
        assert message.content == "How do I treat a burn?"
        assert message.tool_calls is None
        assert message.tool_results is None