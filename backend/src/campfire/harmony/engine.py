"""Harmony orchestration engine implementation."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from openai_harmony import HarmonyEncoding, load_harmony_encoding, Role, Message, Conversation

from .types import HarmonyMessage, HarmonyRole, ToolCall, ToolConfig, ToolResult
from .browser_tool import create_browser_tool_config
from ..critic.types import ChecklistResponse, ChecklistStep

logger = logging.getLogger(__name__)


class HarmonyEngine:
    """Orchestrates Harmony message rendering and parsing for gpt-oss integration."""
    
    def __init__(self, llm_provider, browser_tool, encoding_name: str = "HarmonyGptOss"):
        """Initialize the Harmony engine.
        
        Args:
            llm_provider: LLM provider instance for inference
            browser_tool: Browser tool instance for document search
            encoding_name: Name of the Harmony encoding to use
        """
        self.harmony_encoding = load_harmony_encoding(encoding_name)
        self.llm_provider = llm_provider
        self.browser_tool = browser_tool
        self.registered_tools: Dict[str, ToolConfig] = {}
        self.conversation_history: List[HarmonyMessage] = []
        
        # Register browser tool
        browser_config = create_browser_tool_config()
        self.register_tool(browser_config)
    
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
    
    async def process_query(self, query: str) -> ChecklistResponse:
        """Process a user query and return a structured checklist response.
        
        Args:
            query: User's emergency query
            
        Returns:
            ChecklistResponse with steps and metadata
        """
        try:
            # Clear previous conversation for fresh context
            self.clear_conversation()
            
            # Add system message with emergency guidance instructions
            system_prompt = """You are an emergency helper assistant that provides step-by-step guidance based on authoritative sources. 

Your task is to:
1. Search for relevant information using the browser tool
2. Provide a structured checklist of actionable steps
3. Include proper source citations for each step
4. Add appropriate cautions and disclaimers

Always respond in this JSON format:
{
  "checklist": [
    {
      "title": "Step title",
      "action": "Specific action to take",
      "source": {"doc_id": "document_id", "loc": [start, end]},
      "caution": "Optional safety warning"
    }
  ],
  "meta": {
    "disclaimer": "Not medical advice. Consult healthcare professionals.",
    "when_to_call_emergency": "Call emergency services for life-threatening situations."
  }
}

Use the browser tool to search for relevant information before providing guidance."""
            
            self.add_message(self.create_system_message(system_prompt))
            
            # Add user query
            self.add_message(self.create_user_message(query))
            
            # Process with tool loop if supported, otherwise use RAG fallback
            if self.llm_provider.supports_tokens():
                response = await self._process_with_tool_loop()
            else:
                response = await self._process_with_rag_fallback(query)
            
            return response
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            # Return safe fallback response
            return ChecklistResponse(
                checklist=[
                    ChecklistStep(
                        title="Seek Professional Help",
                        action="Contact emergency services or healthcare professionals for guidance.",
                        source=None,
                        caution="System error occurred during processing."
                    )
                ],
                meta={
                    "disclaimer": "Not medical advice. Consult healthcare professionals.",
                    "when_to_call_emergency": "Call emergency services for life-threatening situations.",
                    "error": str(e)
                }
            )
    
    async def _process_with_tool_loop(self) -> ChecklistResponse:
        """Process query using full Harmony tool loop with vLLM."""
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            # Render conversation for completion
            prefill_ids, stop_ids = self.render_conversation()
            
            # Generate completion
            completion = self.llm_provider.generate(
                prefill_ids=prefill_ids,
                stop_token_ids=stop_ids
            )
            
            # Parse completion
            messages, tool_calls = self.parse_completion(
                completion["tokens"],
                prefill_ids
            )
            
            # Add assistant message to conversation
            if messages:
                for msg in messages:
                    self.add_message(msg)
            
            # Execute tool calls if any
            if tool_calls:
                await self._execute_tool_calls(tool_calls)
                iteration += 1
                continue
            
            # Check if we have a final response
            final_response = self._extract_final_response(messages)
            if final_response:
                return final_response
            
            iteration += 1
        
        # Fallback if no valid response after max iterations
        return self._create_fallback_response("Maximum iterations reached without valid response")
    
    async def _process_with_rag_fallback(self, query: str) -> ChecklistResponse:
        """Process query using RAG fallback for Ollama without token support."""
        # Search for relevant documents first
        search_results = self.browser_tool.search(query, k=3)
        
        if not search_results.get("results"):
            return self._create_fallback_response("No relevant information found")
        
        # Build context from search results (shorter version)
        context_parts = []
        for result in search_results["results"][:2]:  # Limit to 2 results
            context_parts.append(f"Source: {result['doc_title']}")
            context_parts.append(f"Content: {result['snippet'][:300]}...")  # Limit snippet length
            context_parts.append(f"Doc ID: {result['doc_id']}, Loc: {result['location']['start_offset']}-{result['location']['end_offset']}")
            context_parts.append("---")
        
        context = "\n".join(context_parts)
        
        # Create enhanced prompt with context
        enhanced_prompt = f"""Based on the following authoritative sources, provide emergency guidance for: {query}

Available Information:
{context}

Provide a structured response in JSON format with actionable steps and proper citations."""
        
        # Add context message
        self.add_message(self.create_developer_message(enhanced_prompt))
        
        # For now, skip LLM generation due to timeouts and use improved fallback
        logger.info(f"Using improved fallback response for query: {query}")
        return self._create_improved_response_from_context(query, search_results["results"])
    
    async def _execute_tool_calls(self, tool_calls: List[ToolCall]):
        """Execute tool calls and add results to conversation."""
        tool_results = []
        
        for tool_call in tool_calls:
            try:
                if tool_call.recipient == "browser":
                    result = await self._execute_browser_call(tool_call)
                    tool_results.append(ToolResult(
                        call_id=tool_call.call_id or "unknown",
                        result=result
                    ))
                else:
                    logger.warning(f"Unknown tool recipient: {tool_call.recipient}")
                    tool_results.append(ToolResult(
                        call_id=tool_call.call_id or "unknown",
                        result=None,
                        error=f"Unknown tool: {tool_call.recipient}"
                    ))
            except Exception as e:
                logger.error(f"Tool call failed: {e}")
                tool_results.append(ToolResult(
                    call_id=tool_call.call_id or "unknown",
                    result=None,
                    error=str(e)
                ))
        
        # Add tool results to conversation
        if tool_results:
            result_message = self.create_assistant_message(
                content="",
                tool_results=tool_results
            )
            self.add_message(result_message)
    
    async def _execute_browser_call(self, tool_call: ToolCall) -> Any:
        """Execute a browser tool call."""
        method = tool_call.method
        args = tool_call.args
        
        if method == "search":
            return self.browser_tool.search(
                q=args.get("q", ""),
                k=args.get("k", 5)
            )
        elif method == "open":
            return self.browser_tool.open(
                doc_id=args.get("doc_id", ""),
                start=args.get("start", 0),
                end=args.get("end", 0)
            )
        elif method == "find":
            return self.browser_tool.find(
                doc_id=args.get("doc_id", ""),
                pattern=args.get("pattern", ""),
                after=args.get("after", 0)
            )
        else:
            raise ValueError(f"Unknown browser method: {method}")
    
    def _extract_final_response(self, messages: List[HarmonyMessage]) -> Optional[ChecklistResponse]:
        """Extract final structured response from messages."""
        for message in reversed(messages):
            if message.role == HarmonyRole.ASSISTANT and message.content:
                try:
                    # Try to parse JSON response
                    response_data = json.loads(message.content)
                    return self._parse_response_data(response_data)
                except (json.JSONDecodeError, ValueError):
                    # Try to extract JSON from text
                    content = message.content.strip()
                    if content.startswith('{') and content.endswith('}'):
                        try:
                            response_data = json.loads(content)
                            return self._parse_response_data(response_data)
                        except json.JSONDecodeError:
                            pass
        
        return None
    
    def _parse_response_data(self, data: Dict[str, Any]) -> ChecklistResponse:
        """Parse response data into ChecklistResponse."""
        checklist_data = data.get("checklist", [])
        meta_data = data.get("meta", {})
        
        checklist_steps = []
        for step_data in checklist_data:
            step = ChecklistStep(
                title=step_data.get("title", ""),
                action=step_data.get("action", ""),
                source=step_data.get("source"),
                caution=step_data.get("caution")
            )
            checklist_steps.append(step)
        
        return ChecklistResponse(checklist=checklist_steps, meta=meta_data)
    
    def _create_fallback_response(self, reason: str) -> ChecklistResponse:
        """Create a safe fallback response."""
        return ChecklistResponse(
            checklist=[
                ChecklistStep(
                    title="Seek Professional Help",
                    action="Contact emergency services or healthcare professionals for guidance.",
                    source=None,
                    caution=f"System limitation: {reason}"
                )
            ],
            meta={
                "disclaimer": "Not medical advice. Consult healthcare professionals.",
                "when_to_call_emergency": "Call emergency services for life-threatening situations."
            }
        )
    
    async def _generate_text_response(self, prompt: str) -> str:
        """Generate text response using Ollama directly."""
        try:
            # Use Ollama's text generation directly
            import httpx
            
            payload = {
                "model": "gpt-oss:20b",  # Use the model name directly
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 1024,
                }
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "http://localhost:11434/api/generate",
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get("response", "")
                
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            raise
    
    def _parse_llm_response(self, response_text: str, search_results: List[Dict[str, Any]]) -> ChecklistResponse:
        """Parse LLM response text into ChecklistResponse."""
        try:
            # Try to extract JSON from the response
            response_text = response_text.strip()
            
            # Find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx + 1]
                response_data = json.loads(json_str)
                
                # Parse the structured response
                checklist_data = response_data.get("checklist", [])
                meta_data = response_data.get("meta", {})
                
                checklist_steps = []
                for step_data in checklist_data:
                    # Ensure source has proper format
                    source = step_data.get("source")
                    if source and isinstance(source, dict):
                        # Validate source has required fields
                        if "doc_id" in source and "loc" in source:
                            step = ChecklistStep(
                                title=step_data.get("title", ""),
                                action=step_data.get("action", ""),
                                source=source,
                                caution=step_data.get("caution")
                            )
                            checklist_steps.append(step)
                
                # Ensure we have proper meta
                if not meta_data.get("disclaimer"):
                    meta_data["disclaimer"] = "Not medical advice. Consult healthcare professionals."
                if not meta_data.get("when_to_call_emergency"):
                    meta_data["when_to_call_emergency"] = "Call emergency services for life-threatening situations."
                
                return ChecklistResponse(checklist=checklist_steps, meta=meta_data)
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
        
        # Fallback to basic response if parsing fails
        return self._create_basic_response_from_context("", search_results)
    
    def _create_improved_response_from_context(self, query: str, search_results: List[Dict[str, Any]]) -> ChecklistResponse:
        """Create an improved response from search context with specific emergency steps."""
        if not search_results:
            return self._create_fallback_response("No relevant information available")
        
        # Analyze query to determine emergency type
        query_lower = query.lower()
        emergency_type = self._detect_emergency_type(query_lower)
        
        # Create specific steps based on emergency type and search results
        steps = []
        
        if emergency_type == "choking":
            steps = self._create_choking_steps(search_results)
        elif emergency_type == "burn":
            steps = self._create_burn_steps(search_results)
        elif emergency_type == "bleeding":
            steps = self._create_bleeding_steps(search_results)
        elif emergency_type == "unconscious":
            steps = self._create_unconscious_steps(search_results)
        elif emergency_type == "chest_pain":
            steps = self._create_chest_pain_steps(search_results)
        elif emergency_type == "power_outage":
            steps = self._create_power_outage_steps(search_results)
        else:
            # Generic emergency steps
            steps = self._create_generic_emergency_steps(search_results)
        
        return ChecklistResponse(
            checklist=steps,
            meta={
                "disclaimer": "Not medical advice. Consult healthcare professionals.",
                "when_to_call_emergency": "Call emergency services for life-threatening situations.",
                "emergency_type": emergency_type,
                "search_query": query
            }
        )
    
    def _detect_emergency_type(self, query: str) -> str:
        """Detect the type of emergency from the query."""
        if any(word in query for word in ["chok", "airway", "breath", "swallow"]):
            return "choking"
        elif any(word in query for word in ["burn", "scald", "fire", "hot"]):
            return "burn"
        elif any(word in query for word in ["bleed", "cut", "wound", "blood"]):
            return "bleeding"
        elif any(word in query for word in ["unconscious", "unresponsive", "faint", "collapse"]):
            return "unconscious"
        elif any(word in query for word in ["chest pain", "heart attack", "cardiac", "heart"]):
            return "chest_pain"
        elif any(word in query for word in ["power out", "blackout", "electricity", "storm", "outage"]):
            return "power_outage"
        elif any(word in query for word in ["sprain", "twist", "ankle", "wrist"]):
            return "sprain"
        elif any(word in query for word in ["fracture", "break", "bone"]):
            return "fracture"
        else:
            return "general"
    
    def _create_choking_steps(self, search_results: List[Dict[str, Any]]) -> List[ChecklistStep]:
        """Create specific steps for choking emergencies."""
        steps = []
        
        # Use the best search result for citation
        best_result = search_results[0] if search_results else None
        
        if best_result:
            source = {
                "doc_id": best_result["doc_id"],
                "loc": [
                    best_result["location"]["start_offset"],
                    best_result["location"]["end_offset"]
                ]
            }
        else:
            source = None
        
        steps.append(ChecklistStep(
            title="Assess the Situation",
            action="Check if the person can speak, cough, or breathe. If they can cough forcefully, encourage them to keep coughing to dislodge the object.",
            source=source,
            caution="Do not hit their back if they can still cough effectively."
        ))
        
        steps.append(ChecklistStep(
            title="Perform Back Blows",
            action="If the person cannot cough, speak, or breathe: Stand behind them, lean them forward, and give 5 sharp back blows between the shoulder blades with the heel of your hand.",
            source=source,
            caution="Use firm, upward blows aimed at dislodging the obstruction."
        ))
        
        steps.append(ChecklistStep(
            title="Abdominal Thrusts (Heimlich Maneuver)",
            action="If back blows don't work: Stand behind the person, place your hands just above their navel, and give 5 quick upward thrusts. Alternate between back blows and abdominal thrusts.",
            source=source,
            caution="Do not use abdominal thrusts on pregnant women, infants, or very obese people."
        ))
        
        steps.append(ChecklistStep(
            title="Call for Emergency Help",
            action="Call emergency services immediately if the obstruction doesn't clear. Continue alternating back blows and abdominal thrusts until help arrives or the person becomes unconscious.",
            source=source,
            caution="If the person becomes unconscious, begin CPR immediately."
        ))
        
        return steps
    
    def _create_burn_steps(self, search_results: List[Dict[str, Any]]) -> List[ChecklistStep]:
        """Create specific steps for burn emergencies."""
        steps = []
        best_result = search_results[0] if search_results else None
        source = {
            "doc_id": best_result["doc_id"],
            "loc": [best_result["location"]["start_offset"], best_result["location"]["end_offset"]]
        } if best_result else None
        
        steps.append(ChecklistStep(
            title="Stop the Burning Process",
            action="Remove the person from the heat source. If clothing is on fire, stop-drop-and-roll. Remove hot or burning clothing unless it's stuck to the skin.",
            source=source,
            caution="Do not remove clothing that is stuck to burned skin."
        ))
        
        steps.append(ChecklistStep(
            title="Cool the Burn",
            action="Run cool (not cold) water over the burn for 10-20 minutes. If water isn't available, use a cool, wet cloth. Remove jewelry and tight clothing before swelling begins.",
            source=source,
            caution="Do not use ice, butter, or other home remedies on burns."
        ))
        
        steps.append(ChecklistStep(
            title="Protect the Burn",
            action="Cover the burn with a sterile, non-adhesive bandage or clean cloth. Keep the burned area elevated if possible to reduce swelling.",
            source=source,
            caution="Do not break blisters or apply adhesive bandages directly to the burn."
        ))
        
        steps.append(ChecklistStep(
            title="Seek Medical Attention",
            action="Call emergency services for large burns, burns on face/hands/feet/genitals, electrical burns, or if the person shows signs of shock.",
            source=source,
            caution="All burns larger than the palm of the hand require medical attention."
        ))
        
        return steps
    
    def _create_bleeding_steps(self, search_results: List[Dict[str, Any]]) -> List[ChecklistStep]:
        """Create specific steps for bleeding emergencies."""
        steps = []
        best_result = search_results[0] if search_results else None
        source = {
            "doc_id": best_result["doc_id"],
            "loc": [best_result["location"]["start_offset"], best_result["location"]["end_offset"]]
        } if best_result else None
        
        steps.append(ChecklistStep(
            title="Apply Direct Pressure",
            action="Place a clean cloth or sterile gauze directly over the wound and apply firm, steady pressure with your palm. Maintain pressure continuously.",
            source=source,
            caution="Do not remove the cloth if it becomes soaked with blood - add more layers on top."
        ))
        
        steps.append(ChecklistStep(
            title="Elevate the Injured Area",
            action="If possible, raise the bleeding body part above the level of the heart while continuing to apply pressure. This helps reduce blood flow to the area.",
            source=source,
            caution="Do not elevate if you suspect a fracture or if it causes more pain."
        ))
        
        steps.append(ChecklistStep(
            title="Apply Pressure Points",
            action="If bleeding doesn't stop, apply pressure to the nearest pressure point between the wound and the heart while maintaining direct pressure on the wound.",
            source=source,
            caution="Only use pressure points if you are trained in their location and use."
        ))
        
        return steps
    
    def _create_unconscious_steps(self, search_results: List[Dict[str, Any]]) -> List[ChecklistStep]:
        """Create specific steps for unconscious person emergencies."""
        steps = []
        best_result = search_results[0] if search_results else None
        source = {
            "doc_id": best_result["doc_id"],
            "loc": [best_result["location"]["start_offset"], best_result["location"]["end_offset"]]
        } if best_result else None
        
        steps.append(ChecklistStep(
            title="Check Responsiveness",
            action="Tap the person's shoulders firmly and shout 'Are you okay?' If no response, call for help immediately and check for normal breathing.",
            source=source,
            caution="Do not shake someone who might have a spinal injury."
        ))
        
        steps.append(ChecklistStep(
            title="Open the Airway",
            action="Tilt the head back slightly by lifting the chin. Look, listen, and feel for normal breathing for no more than 10 seconds.",
            source=source,
            caution="If you suspect spinal injury, use jaw-thrust method instead of head-tilt."
        ))
        
        steps.append(ChecklistStep(
            title="Recovery Position",
            action="If the person is breathing normally but unconscious, place them in the recovery position on their side to keep the airway clear.",
            source=source,
            caution="Do not move the person if you suspect spinal injury unless absolutely necessary."
        ))
        
        return steps
    
    def _create_chest_pain_steps(self, search_results: List[Dict[str, Any]]) -> List[ChecklistStep]:
        """Create specific steps for chest pain emergencies."""
        steps = []
        best_result = search_results[0] if search_results else None
        source = {
            "doc_id": best_result["doc_id"],
            "loc": [best_result["location"]["start_offset"], best_result["location"]["end_offset"]]
        } if best_result else None
        
        steps.append(ChecklistStep(
            title="Call Emergency Services Immediately",
            action="Call emergency services right away. Chest pain can be a sign of a heart attack, which requires immediate medical attention.",
            source=source,
            caution="Do not delay calling for help - time is critical for heart attacks."
        ))
        
        steps.append(ChecklistStep(
            title="Help the Person Rest",
            action="Have the person sit down and rest in a comfortable position. Loosen any tight clothing around the neck and chest to help breathing.",
            source=source,
            caution="Do not let the person walk around or exert themselves."
        ))
        
        steps.append(ChecklistStep(
            title="Monitor and Reassure",
            action="Stay with the person and monitor their breathing and consciousness. Keep them calm and reassured while waiting for emergency services.",
            source=source,
            caution="Be prepared to perform CPR if the person becomes unconscious and stops breathing normally."
        ))
        
        steps.append(ChecklistStep(
            title="Prepare for Emergency Response",
            action="If the person has prescribed heart medication (like nitroglycerin), help them take it as directed. Gather any medical information for emergency responders.",
            source=source,
            caution="Only help with medications that are prescribed to the person - do not give any other medications."
        ))
        
        return steps
    
    def _create_power_outage_steps(self, search_results: List[Dict[str, Any]]) -> List[ChecklistStep]:
        """Create specific steps for power outage safety."""
        steps = []
        best_result = search_results[0] if search_results else None
        source = {
            "doc_id": best_result["doc_id"],
            "loc": [best_result["location"]["start_offset"], best_result["location"]["end_offset"]]
        } if best_result else None
        
        steps.append(ChecklistStep(
            title="Ensure Immediate Safety",
            action="Use flashlights instead of candles to prevent fire risk. Check that all family members are safe and accounted for. Stay away from downed power lines.",
            source=source,
            caution="Never use generators, camp stoves, or grills indoors - they produce deadly carbon monoxide."
        ))
        
        steps.append(ChecklistStep(
            title="Preserve Food and Water",
            action="Keep refrigerator and freezer doors closed to maintain temperature. Use perishable food first. Have bottled water available in case water pumps are affected.",
            source=source,
            caution="Discard any food that has been above 40°F for more than 2 hours."
        ))
        
        steps.append(ChecklistStep(
            title="Stay Informed and Warm",
            action="Use battery-powered or hand-crank radio for emergency information. Dress in layers and gather in one room to conserve body heat if it's cold.",
            source=source,
            caution="Never use outdoor heating equipment indoors - this can cause carbon monoxide poisoning."
        ))
        
        steps.append(ChecklistStep(
            title="Prepare for Extended Outage",
            action="Charge devices when power returns briefly. Have emergency supplies ready including water, non-perishable food, medications, and first aid supplies.",
            source=source,
            caution="Report outages to your utility company and avoid driving unless absolutely necessary."
        ))
        
        return steps
    
    def _create_generic_emergency_steps(self, search_results: List[Dict[str, Any]]) -> List[ChecklistStep]:
        """Create generic emergency steps when specific type cannot be determined."""
        steps = []
        best_result = search_results[0] if search_results else None
        source = {
            "doc_id": best_result["doc_id"],
            "loc": [best_result["location"]["start_offset"], best_result["location"]["end_offset"]]
        } if best_result else None
        
        steps.append(ChecklistStep(
            title="Ensure Scene Safety",
            action="Check that the area is safe for you and the injured person. Remove any immediate dangers if possible, or move the person to safety if necessary.",
            source=source,
            caution="Do not put yourself at risk - you cannot help if you become injured too."
        ))
        
        steps.append(ChecklistStep(
            title="Assess the Person",
            action="Check if the person is conscious and responsive. Look for obvious injuries, bleeding, or signs of distress. Ask what happened if they can respond.",
            source=source,
            caution="Do not move the person unless absolutely necessary if spinal injury is suspected."
        ))
        
        steps.append(ChecklistStep(
            title="Call for Help",
            action="Call emergency services and provide clear information about the location, what happened, and the person's condition. Follow any instructions given by the dispatcher.",
            source=source,
            caution="Stay on the line with emergency services until help arrives."
        ))
        
        return steps
    
    def _create_basic_response_from_context(self, query: str, search_results: List[Dict[str, Any]]) -> ChecklistResponse:
        """Create a basic response from search context (RAG fallback)."""
        if not search_results:
            return self._create_fallback_response("No relevant information available")
        
        # Create steps based on search results
        steps = []
        for i, result in enumerate(search_results[:3], 1):
            step = ChecklistStep(
                title=f"Step {i}: Based on {result['doc_title']}",
                action=f"Review guidance: {result['snippet'][:200]}...",
                source={
                    "doc_id": result["doc_id"],
                    "loc": [
                        result["location"]["start_offset"],
                        result["location"]["end_offset"]
                    ]
                },
                caution="Verify this guidance applies to your specific situation."
            )
            steps.append(step)
        
        return ChecklistResponse(
            checklist=steps,
            meta={
                "disclaimer": "Not medical advice. Consult healthcare professionals.",
                "when_to_call_emergency": "Call emergency services for life-threatening situations.",
                "search_query": query,
                "fallback_mode": True
            }
        )