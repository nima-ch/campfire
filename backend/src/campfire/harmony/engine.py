"""Harmony orchestration engine implementation."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from openai_harmony import HarmonyEncoding, load_harmony_encoding, Role, Message, Conversation

from .types import HarmonyMessage, HarmonyRole, ToolCall, ToolConfig, ToolResult

logger = logging.getLogger(__name__)


class HarmonyEngine:
    """Orchestrates Harmony message rendering and parsing for gpt-oss integration."""
    
    def __init__(self, encoding_name: str = "HarmonyGptOss"):
        """Initialize the Harmony engine.
        
        Args:
            encoding_name: Name of the Harmony encoding to use
        """
        self.harmony_encoding = load_harmony_encoding(encoding_name)
        self.registered_tools: Dict[str, ToolConfig] = {}
        self.conversation_history: List[HarmonyMessage] = []
    
    def register_tool(self, tool_config: ToolConfig) -> None:
        """Register a tool for use in Harmony conversations.
        
        Args:
            tool_config: Tool configuration with recipient prefix and definition
        """
        self.registered_tools[tool_config.recipient_prefix] = tool_config
        logger.info(f"Registered tool: {tool_config.recipient_prefix}")
    
    def add_message(self, message: HarmonyMessage) -> None:
        """Add a message to the conversation history.
        
        Args:
            message: Message to add to conversation
        """
        self.conversation_history.append(message)
        logger.debug(f"Added message: {message.role} - {len(message.content)} chars")
    
    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        self.conversation_history.clear()
        logger.debug("Cleared conversation history")
    
    def render_conversation(
        self, 
        messages: Optional[List[HarmonyMessage]] = None,
        include_tools: bool = True
    ) -> Tuple[List[int], List[int]]:
        """Render conversation messages to token IDs for model input.
        
        Args:
            messages: Messages to render (uses conversation_history if None)
            include_tools: Whether to include tool configurations
            
        Returns:
            Tuple of (prefill_token_ids, stop_token_ids)
        """
        if messages is None:
            messages = self.conversation_history
            
        # Convert messages to Harmony format
        harmony_messages = []
        for msg in messages:
            harmony_msg = {
                "role": msg.role.value,
                "content": msg.content
            }
            
            # Add tool calls if present
            if msg.tool_calls:
                harmony_msg["tool_calls"] = [
                    {
                        "recipient": tc.recipient,
                        "method": tc.method,
                        "args": tc.args,
                        "call_id": tc.call_id
                    }
                    for tc in msg.tool_calls
                ]
            
            # Add tool results if present
            if msg.tool_results:
                harmony_msg["tool_results"] = [
                    {
                        "call_id": tr.call_id,
                        "result": tr.result,
                        "error": tr.error
                    }
                    for tr in msg.tool_results
                ]
            
            harmony_messages.append(harmony_msg)
        
        # Prepare tool configurations
        tool_configs = []
        if include_tools:
            for tool_config in self.registered_tools.values():
                tool_configs.append({
                    "recipient_prefix": tool_config.recipient_prefix,
                    "definition": {
                        "name": tool_config.definition.name,
                        "methods": tool_config.definition.methods
                    }
                })
        
        # Render using Harmony
        try:
            # Convert messages to openai-harmony Message objects
            harmony_message_objects = []
            for msg in harmony_messages:
                # Convert role string to Role enum
                role_map = {
                    "system": Role.SYSTEM,
                    "developer": Role.DEVELOPER,
                    "user": Role.USER,
                    "assistant": Role.ASSISTANT
                }
                role = role_map.get(msg["role"], Role.USER)
                
                # Create Message object
                message_obj = Message.from_role_and_content(role, msg["content"])
                harmony_message_objects.append(message_obj)
            
            # Create Conversation object
            conversation = Conversation.from_messages(harmony_message_objects)
            
            # Render the conversation for completion
            prefill_ids = self.harmony_encoding.render_conversation_for_completion(
                conversation,
                next_turn_role=Role.ASSISTANT
            )
            
            # Get stop tokens for assistant actions
            stop_ids = self.harmony_encoding.stop_tokens_for_assistant_actions()
            
            logger.debug(f"Rendered {len(prefill_ids)} prefill tokens, {len(stop_ids)} stop tokens")
            return prefill_ids, stop_ids
            
        except Exception as e:
            logger.error(f"Failed to render conversation: {e}")
            raise RuntimeError(f"Harmony rendering failed: {e}") from e
    
    def parse_completion(
        self, 
        completion_tokens: List[int],
        original_prefill_ids: List[int]
    ) -> Tuple[List[HarmonyMessage], List[ToolCall]]:
        """Parse completion tokens back to structured messages and tool calls.
        
        Args:
            completion_tokens: Token IDs from model completion
            original_prefill_ids: Original prefill token IDs used for generation
            
        Returns:
            Tuple of (parsed_messages, extracted_tool_calls)
        """
        try:
            # Parse completion using Harmony
            parsed_messages = self.harmony_encoding.parse_messages_from_completion_tokens(
                completion_tokens
            )
            
            messages = []
            tool_calls = []
            
            # Extract messages
            for msg_data in parsed_messages:
                # Parse tool calls if present
                msg_tool_calls = None
                if hasattr(msg_data, 'tool_calls') and msg_data.tool_calls:
                    msg_tool_calls = [
                        ToolCall(
                            recipient=tc.recipient,
                            method=tc.method,
                            args=tc.args,
                            call_id=getattr(tc, 'call_id', None)
                        )
                        for tc in msg_data.tool_calls
                    ]
                    tool_calls.extend(msg_tool_calls)
                
                # Parse tool results if present
                msg_tool_results = None
                if hasattr(msg_data, 'tool_results') and msg_data.tool_results:
                    msg_tool_results = [
                        ToolResult(
                            call_id=tr.call_id,
                            result=tr.result,
                            error=getattr(tr, 'error', None)
                        )
                        for tr in msg_data.tool_results
                    ]
                
                # Get content - it might be a list of content objects
                content = ""
                if hasattr(msg_data, 'content'):
                    if isinstance(msg_data.content, list):
                        # Extract text from content objects
                        content_parts = []
                        for content_obj in msg_data.content:
                            if hasattr(content_obj, 'text'):
                                content_parts.append(content_obj.text)
                        content = "".join(content_parts)
                    else:
                        content = str(msg_data.content)
                
                message = HarmonyMessage(
                    role=HarmonyRole(msg_data.role.value),
                    content=content,
                    tool_calls=msg_tool_calls,
                    tool_results=msg_tool_results
                )
                messages.append(message)
            
            logger.debug(f"Parsed {len(messages)} messages, {len(tool_calls)} tool calls")
            return messages, tool_calls
            
        except Exception as e:
            logger.error(f"Failed to parse completion: {e}")
            raise RuntimeError(f"Harmony parsing failed: {e}") from e
    
    def create_system_message(self, content: str) -> HarmonyMessage:
        """Create a system message.
        
        Args:
            content: System message content
            
        Returns:
            System message
        """
        return HarmonyMessage(role=HarmonyRole.SYSTEM, content=content)
    
    def create_developer_message(self, content: str) -> HarmonyMessage:
        """Create a developer message.
        
        Args:
            content: Developer message content
            
        Returns:
            Developer message
        """
        return HarmonyMessage(role=HarmonyRole.DEVELOPER, content=content)
    
    def create_user_message(self, content: str) -> HarmonyMessage:
        """Create a user message.
        
        Args:
            content: User message content
            
        Returns:
            User message
        """
        return HarmonyMessage(role=HarmonyRole.USER, content=content)
    
    def create_assistant_message(
        self, 
        content: str,
        tool_calls: Optional[List[ToolCall]] = None,
        tool_results: Optional[List[ToolResult]] = None
    ) -> HarmonyMessage:
        """Create an assistant message with optional tool calls/results.
        
        Args:
            content: Assistant message content
            tool_calls: Optional tool calls made by assistant
            tool_results: Optional tool results from previous calls
            
        Returns:
            Assistant message
        """
        return HarmonyMessage(
            role=HarmonyRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results
        )
    
    def handle_multi_turn_conversation(
        self,
        new_message: HarmonyMessage,
        max_history: int = 10
    ) -> Tuple[List[int], List[int]]:
        """Handle multi-turn conversation by adding message and rendering.
        
        Args:
            new_message: New message to add to conversation
            max_history: Maximum number of messages to keep in history
            
        Returns:
            Tuple of (prefill_token_ids, stop_token_ids)
        """
        # Add new message to conversation
        self.add_message(new_message)
        
        # Trim conversation history if needed
        if len(self.conversation_history) > max_history:
            # Keep system messages and trim from the middle
            system_messages = [
                msg for msg in self.conversation_history 
                if msg.role == HarmonyRole.SYSTEM
            ]
            other_messages = [
                msg for msg in self.conversation_history 
                if msg.role != HarmonyRole.SYSTEM
            ]
            
            # Keep most recent messages
            recent_messages = other_messages[-(max_history - len(system_messages)):]
            self.conversation_history = system_messages + recent_messages
            
            logger.debug(f"Trimmed conversation to {len(self.conversation_history)} messages")
        
        # Render the conversation
        return self.render_conversation()
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the current conversation state.
        
        Returns:
            Dictionary with conversation statistics
        """
        role_counts = {}
        total_chars = 0
        tool_call_count = 0
        
        for msg in self.conversation_history:
            role_counts[msg.role.value] = role_counts.get(msg.role.value, 0) + 1
            total_chars += len(msg.content)
            if msg.tool_calls:
                tool_call_count += len(msg.tool_calls)
        
        return {
            "message_count": len(self.conversation_history),
            "role_distribution": role_counts,
            "total_characters": total_chars,
            "tool_calls": tool_call_count,
            "registered_tools": list(self.registered_tools.keys())
        }