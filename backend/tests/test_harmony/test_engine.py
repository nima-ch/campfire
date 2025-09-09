"""Tests for Harmony engine implementation."""

import pytest
from unittest.mock import Mock, patch

from campfire.harmony.engine import HarmonyEngine
from campfire.harmony.types import (
    HarmonyMessage, 
    HarmonyRole, 
    ToolCall, 
    ToolConfig, 
    ToolDefinition,
    ToolResult
)
from campfire.harmony.browser_tool import create_browser_tool_config


class TestHarmonyEngine:
    """Test cases for HarmonyEngine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = HarmonyEngine()
    
    def test_initialization(self):
        """Test engine initialization."""
        assert self.engine.registered_tools == {}
        assert self.engine.conversation_history == []
        assert self.engine.harmony_encoding is not None
    
    def test_register_tool(self):
        """Test tool registration."""
        tool_config = create_browser_tool_config()
        
        self.engine.register_tool(tool_config)
        
        assert "browser" in self.engine.registered_tools
        assert self.engine.registered_tools["browser"] == tool_config
    
    def test_add_message(self):
        """Test adding messages to conversation."""
        message = HarmonyMessage(
            role=HarmonyRole.USER,
            content="Test message"
        )
        
        self.engine.add_message(message)
        
        assert len(self.engine.conversation_history) == 1
        assert self.engine.conversation_history[0] == message
    
    def test_clear_conversation(self):
        """Test clearing conversation history."""
        message = HarmonyMessage(
            role=HarmonyRole.USER,
            content="Test message"
        )
        self.engine.add_message(message)
        
        self.engine.clear_conversation()
        
        assert len(self.engine.conversation_history) == 0
    
    def test_create_system_message(self):
        """Test creating system messages."""
        content = "You are a helpful assistant."
        message = self.engine.create_system_message(content)
        
        assert message.role == HarmonyRole.SYSTEM
        assert message.content == content
        assert message.tool_calls is None
        assert message.tool_results is None
    
    def test_create_developer_message(self):
        """Test creating developer messages."""
        content = "Developer instruction"
        message = self.engine.create_developer_message(content)
        
        assert message.role == HarmonyRole.DEVELOPER
        assert message.content == content
    
    def test_create_user_message(self):
        """Test creating user messages."""
        content = "User query"
        message = self.engine.create_user_message(content)
        
        assert message.role == HarmonyRole.USER
        assert message.content == content
    
    def test_create_assistant_message(self):
        """Test creating assistant messages."""
        content = "Assistant response"
        tool_calls = [
            ToolCall(
                recipient="browser",
                method="search",
                args={"q": "test query"},
                call_id="call_1"
            )
        ]
        
        message = self.engine.create_assistant_message(
            content=content,
            tool_calls=tool_calls
        )
        
        assert message.role == HarmonyRole.ASSISTANT
        assert message.content == content
        assert message.tool_calls == tool_calls
    
    @patch('campfire.harmony.engine.load_harmony_encoding')
    def test_render_conversation_success(self, mock_load_encoding):
        """Test successful conversation rendering."""
        # Setup mock
        mock_encoding = Mock()
        mock_load_encoding.return_value = mock_encoding
        mock_encoding.render_conversation_for_completion.return_value = [1, 2, 3]
        mock_encoding.stop_tokens_for_assistant_actions.return_value = [4, 5]
        
        # Create engine with mocked encoding
        engine = HarmonyEngine()
        
        # Add messages
        messages = [
            HarmonyMessage(role=HarmonyRole.SYSTEM, content="System prompt"),
            HarmonyMessage(role=HarmonyRole.USER, content="User query")
        ]
        
        # Render conversation
        prefill_ids, stop_ids = engine.render_conversation(messages)
        
        assert prefill_ids == [1, 2, 3]
        assert stop_ids == [4, 5]
        mock_encoding.render_conversation_for_completion.assert_called_once()
        mock_encoding.stop_tokens_for_assistant_actions.assert_called_once()
    
    @patch('campfire.harmony.engine.load_harmony_encoding')
    def test_render_conversation_with_tools(self, mock_load_encoding):
        """Test conversation rendering with tools."""
        # Setup mock
        mock_encoding = Mock()
        mock_load_encoding.return_value = mock_encoding
        mock_encoding.render_conversation_for_completion.return_value = [1, 2, 3]
        mock_encoding.stop_tokens_for_assistant_actions.return_value = [4, 5]
        
        # Create engine and register tool
        engine = HarmonyEngine()
        tool_config = create_browser_tool_config()
        engine.register_tool(tool_config)
        
        messages = [
            HarmonyMessage(role=HarmonyRole.USER, content="Search for information")
        ]
        
        # Render with tools
        prefill_ids, stop_ids = engine.render_conversation(messages, include_tools=True)
        
        # Verify the method was called with correct parameters
        mock_encoding.render_conversation_for_completion.assert_called_once()
        call_args = mock_encoding.render_conversation_for_completion.call_args
        
        # Check that conversation object was passed
        assert call_args is not None
        assert len(call_args[0]) >= 1  # At least conversation argument
        
        # Verify stop tokens method was called
        mock_encoding.stop_tokens_for_assistant_actions.assert_called_once()
    
    @patch('campfire.harmony.engine.load_harmony_encoding')
    def test_render_conversation_error(self, mock_load_encoding):
        """Test conversation rendering error handling."""
        # Setup mock to raise exception
        mock_encoding = Mock()
        mock_load_encoding.return_value = mock_encoding
        mock_encoding.render_conversation_for_completion.side_effect = Exception("Rendering failed")
        
        engine = HarmonyEngine()
        messages = [
            HarmonyMessage(role=HarmonyRole.USER, content="Test")
        ]
        
        with pytest.raises(RuntimeError, match="Harmony rendering failed"):
            engine.render_conversation(messages)
    
    @patch('campfire.harmony.engine.load_harmony_encoding')
    def test_parse_completion_success(self, mock_load_encoding):
        """Test successful completion parsing."""
        # Setup mock message object
        mock_tool_call = Mock()
        mock_tool_call.recipient = "browser"
        mock_tool_call.method = "search"
        mock_tool_call.args = {"q": "test query"}
        mock_tool_call.call_id = "call_1"
        
        mock_role = Mock()
        mock_role.value = "assistant"
        
        mock_message = Mock()
        mock_message.role = mock_role
        mock_message.content = "I'll search for that information."
        mock_message.tool_calls = [mock_tool_call]
        mock_message.tool_results = None
        
        # Setup mock encoding
        mock_encoding = Mock()
        mock_load_encoding.return_value = mock_encoding
        mock_encoding.parse_messages_from_completion_tokens.return_value = [mock_message]
        
        engine = HarmonyEngine()
        
        # Parse completion
        messages, tool_calls = engine.parse_completion(
            completion_tokens=[10, 11, 12],
            original_prefill_ids=[1, 2, 3]
        )
        
        assert len(messages) == 1
        assert messages[0].role == HarmonyRole.ASSISTANT
        assert messages[0].content == "I'll search for that information."
        assert len(tool_calls) == 1
        assert tool_calls[0].recipient == "browser"
        assert tool_calls[0].method == "search"
        assert tool_calls[0].args == {"q": "test query"}
    
    @patch('campfire.harmony.engine.load_harmony_encoding')
    def test_parse_completion_error(self, mock_load_encoding):
        """Test completion parsing error handling."""
        # Setup mock to raise exception
        mock_encoding = Mock()
        mock_load_encoding.return_value = mock_encoding
        mock_encoding.parse_messages_from_completion_tokens.side_effect = Exception("Parsing failed")
        
        engine = HarmonyEngine()
        
        with pytest.raises(RuntimeError, match="Harmony parsing failed"):
            engine.parse_completion([10, 11, 12], [1, 2, 3])
    
    def test_handle_multi_turn_conversation(self):
        """Test multi-turn conversation handling."""
        # Add some initial messages
        self.engine.add_message(
            HarmonyMessage(role=HarmonyRole.SYSTEM, content="System prompt")
        )
        self.engine.add_message(
            HarmonyMessage(role=HarmonyRole.USER, content="First query")
        )
        
        # Mock the render method to avoid actual Harmony calls
        with patch.object(self.engine, 'render_conversation') as mock_render:
            mock_render.return_value = ([1, 2, 3], [4, 5])
            
            new_message = HarmonyMessage(
                role=HarmonyRole.USER, 
                content="Second query"
            )
            
            prefill_ids, stop_ids = self.engine.handle_multi_turn_conversation(new_message)
            
            # Verify message was added
            assert len(self.engine.conversation_history) == 3
            assert self.engine.conversation_history[-1] == new_message
            
            # Verify render was called
            mock_render.assert_called_once()
            assert prefill_ids == [1, 2, 3]
            assert stop_ids == [4, 5]
    
    def test_conversation_history_trimming(self):
        """Test conversation history trimming in multi-turn."""
        # Add system message
        system_msg = HarmonyMessage(role=HarmonyRole.SYSTEM, content="System")
        self.engine.add_message(system_msg)
        
        # Add many user messages to exceed max_history
        for i in range(12):
            self.engine.add_message(
                HarmonyMessage(role=HarmonyRole.USER, content=f"Message {i}")
            )
        
        with patch.object(self.engine, 'render_conversation') as mock_render:
            mock_render.return_value = ([1, 2, 3], [4, 5])
            
            new_message = HarmonyMessage(role=HarmonyRole.USER, content="New message")
            
            self.engine.handle_multi_turn_conversation(new_message, max_history=10)
            
            # Should have trimmed to max_history
            assert len(self.engine.conversation_history) == 10
            
            # System message should be preserved
            system_messages = [
                msg for msg in self.engine.conversation_history 
                if msg.role == HarmonyRole.SYSTEM
            ]
            assert len(system_messages) == 1
            assert system_messages[0] == system_msg
    
    def test_get_conversation_summary(self):
        """Test conversation summary generation."""
        # Add various message types
        self.engine.add_message(
            HarmonyMessage(role=HarmonyRole.SYSTEM, content="System prompt")
        )
        self.engine.add_message(
            HarmonyMessage(role=HarmonyRole.USER, content="User query")
        )
        self.engine.add_message(
            HarmonyMessage(
                role=HarmonyRole.ASSISTANT, 
                content="Assistant response",
                tool_calls=[
                    ToolCall(recipient="browser", method="search", args={"q": "test"})
                ]
            )
        )
        
        # Register a tool
        tool_config = create_browser_tool_config()
        self.engine.register_tool(tool_config)
        
        summary = self.engine.get_conversation_summary()
        
        assert summary["message_count"] == 3
        assert summary["role_distribution"]["system"] == 1
        assert summary["role_distribution"]["user"] == 1
        assert summary["role_distribution"]["assistant"] == 1
        assert summary["tool_calls"] == 1
        assert "browser" in summary["registered_tools"]
        assert summary["total_characters"] > 0