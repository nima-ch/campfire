"""
Agent composition system for Campfire emergency helper.

This module implements the core agent orchestration that combines LLM providers,
Harmony tool execution, and structured output parsing to provide emergency guidance
with proper citations from the local document corpus.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from ..llm.base import LLMProvider, GenerationError
from .engine import HarmonyEngine
from .browser import LocalBrowserTool
from .browser_tool import create_browser_tool_config
from .types import HarmonyMessage, HarmonyRole, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class ChecklistStep:
    """Represents a single step in an emergency checklist."""
    
    def __init__(
        self,
        title: str,
        action: str,
        source: Optional[Dict[str, Any]] = None,
        caution: Optional[str] = None
    ):
        self.title = title
        self.action = action
        self.source = source
        self.caution = caution
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "title": self.title,
            "action": self.action
        }
        if self.source:
            result["source"] = self.source
        if self.caution:
            result["caution"] = self.caution
        return result


class ChecklistResponse:
    """Represents a complete emergency response with checklist and metadata."""
    
    def __init__(
        self,
        checklist: List[ChecklistStep],
        disclaimer: str = "Not medical advice. For emergencies, call local emergency services.",
        when_to_call_emergency: Optional[str] = None
    ):
        self.checklist = checklist
        self.disclaimer = disclaimer
        self.when_to_call_emergency = when_to_call_emergency
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "checklist": [step.to_dict() for step in self.checklist],
            "meta": {
                "disclaimer": self.disclaimer
            }
        }
        if self.when_to_call_emergency:
            result["meta"]["when_to_call_emergency"] = self.when_to_call_emergency
        return result


class AgentCompositionSystem:
    """
    Main agent composition system that orchestrates LLM, tools, and safety checks.
    
    Supports two modes:
    1. Tool-loop mode: Full Harmony tool execution for providers with token support
    2. RAG prefetch mode: Fallback mode that prefetches relevant documents
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        corpus_db_path: str,
        max_tool_iterations: int = 5,
        max_tokens: int = 2048,
        temperature: float = 0.1
    ):
        """
        Initialize the agent composition system.
        
        Args:
            llm_provider: LLM provider instance
            corpus_db_path: Path to the corpus database
            max_tool_iterations: Maximum number of tool call iterations
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
        """
        self.llm_provider = llm_provider
        self.corpus_db_path = corpus_db_path
        self.max_tool_iterations = max_tool_iterations
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Initialize Harmony engine
        self.harmony_engine = HarmonyEngine()
        
        # Initialize browser tool
        self.browser_tool = LocalBrowserTool(corpus_db_path)
        
        # Register browser tool with Harmony
        browser_config = create_browser_tool_config()
        self.harmony_engine.register_tool(browser_config)
        
        # System prompt for emergency guidance
        self.system_prompt = """You are an emergency guidance assistant that provides step-by-step checklists for household and community emergencies. You have access to a local document corpus containing IFRC First Aid Guidelines (2020) and WHO Psychological First Aid (2011).

CRITICAL REQUIREMENTS:
1. Always provide responses as a structured checklist with clear, actionable steps
2. Every step MUST include a source citation from the document corpus
3. Use the browser tool to search, open, and find relevant information
4. Include appropriate safety warnings and disclaimers
5. For life-threatening situations, always advise calling emergency services

Use the browser tool methods:
- search(q, k): Search for relevant information
- open(doc_id, start, end): Get specific text from a document
- find(doc_id, pattern, after): Find patterns within a document

Format your final response as JSON:
{
  "checklist": [
    {
      "title": "Step title",
      "action": "Detailed action to take",
      "source": {
        "doc_id": "document_id",
        "loc": [start_offset, end_offset]
      },
      "caution": "Optional safety warning"
    }
  ],
  "meta": {
    "disclaimer": "Not medical advice. For emergencies, call local emergency services.",
    "when_to_call_emergency": "Specific conditions requiring emergency services"
  }
}"""
    
    def process_query(self, query: str) -> ChecklistResponse:
        """
        Process an emergency query and return a structured checklist response.
        
        Args:
            query: User's emergency query
            
        Returns:
            ChecklistResponse with actionable steps and citations
        """
        try:
            if self.llm_provider.supports_tokens():
                return self._process_with_tool_loop(query)
            else:
                return self._process_with_rag_fallback(query)
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return self._create_error_response(str(e))
    
    def _process_with_tool_loop(self, query: str) -> ChecklistResponse:
        """
        Process query using full Harmony tool-loop mode.
        
        This mode allows the LLM to make multiple tool calls and iterate
        based on the results, providing the most accurate responses.
        """
        logger.info("Processing query with tool-loop mode")
        
        # Clear previous conversation
        self.harmony_engine.clear_conversation()
        
        # Add system message
        system_msg = self.harmony_engine.create_system_message(self.system_prompt)
        self.harmony_engine.add_message(system_msg)
        
        # Add user query
        user_msg = self.harmony_engine.create_user_message(query)
        self.harmony_engine.add_message(user_msg)
        
        # Execute tool loop
        for iteration in range(self.max_tool_iterations):
            logger.debug(f"Tool loop iteration {iteration + 1}")
            
            try:
                # Render conversation for completion
                prefill_ids, stop_ids = self.harmony_engine.render_conversation()
                
                # Generate completion
                result = self.llm_provider.generate(
                    prefill_ids=prefill_ids,
                    stop_token_ids=stop_ids,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )
                
                # Parse completion
                messages, tool_calls = self.harmony_engine.parse_completion(
                    completion_tokens=result["completion_tokens"],
                    original_prefill_ids=prefill_ids
                )
                
                # Add parsed messages to conversation
                for message in messages:
                    self.harmony_engine.add_message(message)
                
                # If no tool calls, we're done
                if not tool_calls:
                    break
                
                # Execute tool calls
                tool_results = self._execute_tool_calls(tool_calls)
                
                # Add tool results to conversation
                if tool_results:
                    result_msg = self.harmony_engine.create_assistant_message(
                        content="",
                        tool_results=tool_results
                    )
                    self.harmony_engine.add_message(result_msg)
                
            except Exception as e:
                logger.error(f"Tool loop iteration {iteration + 1} failed: {e}")
                break
        
        # Extract final response
        return self._extract_checklist_response()
    
    def _process_with_rag_fallback(self, query: str) -> ChecklistResponse:
        """
        Process query using RAG prefetch fallback mode.
        
        This mode prefetches relevant documents and includes them in the prompt
        for providers that don't support token-level tool execution.
        """
        logger.info("Processing query with RAG fallback mode")
        
        try:
            # Search for relevant documents
            search_results = self.browser_tool.search(query, k=3)
            
            # Gather relevant context
            context_parts = []
            for result in search_results.get("results", []):
                # Get more context from each relevant document
                doc_id = result["doc_id"]
                location = result["location"]
                
                # Expand the context window
                start = max(0, location["start_offset"] - 500)
                end = location["end_offset"] + 500
                
                doc_content = self.browser_tool.open(doc_id, start, end)
                if doc_content.get("status") == "success":
                    context_parts.append({
                        "doc_id": doc_id,
                        "doc_title": doc_content["doc_title"],
                        "text": doc_content["text"],
                        "location": doc_content["location"]
                    })
            
            # Create enhanced prompt with context
            enhanced_prompt = self._create_rag_prompt(query, context_parts)
            
            # Clear conversation and set up for RAG mode
            self.harmony_engine.clear_conversation()
            
            # Add system message
            system_msg = self.harmony_engine.create_system_message(self.system_prompt)
            self.harmony_engine.add_message(system_msg)
            
            # Add enhanced user message with context
            user_msg = self.harmony_engine.create_user_message(enhanced_prompt)
            self.harmony_engine.add_message(user_msg)
            
            # Generate response
            prefill_ids, stop_ids = self.harmony_engine.render_conversation()
            
            # For RAG mode, we need to convert token IDs to text since
            # the provider doesn't support token-level operations
            result = self.llm_provider.generate(
                prefill_ids=prefill_ids,
                stop_token_ids=stop_ids,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Parse the text response directly
            response_text = result["completion_text"]
            return self._parse_text_response(response_text, context_parts)
            
        except Exception as e:
            logger.error(f"RAG fallback processing failed: {e}")
            return self._create_error_response(str(e))
    
    def _execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute a list of tool calls and return results.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of tool results
        """
        results = []
        
        for tool_call in tool_calls:
            try:
                if tool_call.recipient == "browser":
                    result = self._execute_browser_call(tool_call)
                    results.append(ToolResult(
                        call_id=tool_call.call_id or str(uuid.uuid4()),
                        result=result
                    ))
                else:
                    logger.warning(f"Unknown tool recipient: {tool_call.recipient}")
                    results.append(ToolResult(
                        call_id=tool_call.call_id or str(uuid.uuid4()),
                        result=None,
                        error=f"Unknown tool: {tool_call.recipient}"
                    ))
                    
            except Exception as e:
                logger.error(f"Tool call execution failed: {e}")
                results.append(ToolResult(
                    call_id=tool_call.call_id or str(uuid.uuid4()),
                    result=None,
                    error=str(e)
                ))
        
        return results
    
    def _execute_browser_call(self, tool_call: ToolCall) -> Dict[str, Any]:
        """
        Execute a browser tool call.
        
        Args:
            tool_call: Browser tool call to execute
            
        Returns:
            Tool execution result
        """
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
    
    def _create_rag_prompt(self, query: str, context_parts: List[Dict[str, Any]]) -> str:
        """
        Create an enhanced prompt with RAG context.
        
        Args:
            query: Original user query
            context_parts: List of relevant document contexts
            
        Returns:
            Enhanced prompt with context
        """
        prompt_parts = [
            f"User Query: {query}",
            "",
            "Relevant Context from Emergency Guidelines:",
            ""
        ]
        
        for i, context in enumerate(context_parts, 1):
            prompt_parts.extend([
                f"Source {i}: {context['doc_title']}",
                f"Location: {context['location']['start_offset']}-{context['location']['end_offset']}",
                f"Content: {context['text'][:1000]}...",  # Limit context length
                ""
            ])
        
        prompt_parts.extend([
            "Based on the above context, provide a structured checklist response in JSON format.",
            "Ensure each step includes proper source citations with doc_id and location offsets.",
            ""
        ])
        
        return "\n".join(prompt_parts)
    
    def _extract_checklist_response(self) -> ChecklistResponse:
        """
        Extract checklist response from conversation history.
        
        Returns:
            Parsed ChecklistResponse
        """
        # Get the last assistant message
        for message in reversed(self.harmony_engine.conversation_history):
            if message.role == HarmonyRole.ASSISTANT and message.content:
                try:
                    return self._parse_text_response(message.content)
                except Exception as e:
                    logger.error(f"Failed to parse assistant response: {e}")
                    continue
        
        # Fallback if no valid response found
        return self._create_error_response("No valid response generated")
    
    def _parse_text_response(
        self, 
        response_text: str, 
        context_parts: Optional[List[Dict[str, Any]]] = None
    ) -> ChecklistResponse:
        """
        Parse text response into structured ChecklistResponse.
        
        Args:
            response_text: Raw text response from LLM
            context_parts: Optional context for citation mapping
            
        Returns:
            Parsed ChecklistResponse
        """
        try:
            # Try to extract JSON from the response
            json_match = self._extract_json_from_text(response_text)
            if json_match:
                data = json.loads(json_match)
                return self._create_checklist_from_json(data)
            
            # Fallback: parse as structured text
            return self._parse_structured_text(response_text, context_parts)
            
        except Exception as e:
            logger.error(f"Response parsing failed: {e}")
            return self._create_error_response(f"Failed to parse response: {e}")
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """
        Extract JSON content from text response.
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            JSON string if found, None otherwise
        """
        import re
        
        # Look for JSON blocks
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^{}]*"checklist"[^{}]*\{.*?\}[^{}]*\})',
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Try to find JSON-like structure
        brace_count = 0
        start_pos = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    potential_json = text[start_pos:i+1]
                    try:
                        json.loads(potential_json)
                        return potential_json
                    except json.JSONDecodeError:
                        continue
        
        return None
    
    def _create_checklist_from_json(self, data: Dict[str, Any]) -> ChecklistResponse:
        """
        Create ChecklistResponse from parsed JSON data.
        
        Args:
            data: Parsed JSON data
            
        Returns:
            ChecklistResponse object
        """
        checklist_data = data.get("checklist", [])
        meta_data = data.get("meta", {})
        
        steps = []
        for step_data in checklist_data:
            step = ChecklistStep(
                title=step_data.get("title", ""),
                action=step_data.get("action", ""),
                source=step_data.get("source"),
                caution=step_data.get("caution")
            )
            steps.append(step)
        
        return ChecklistResponse(
            checklist=steps,
            disclaimer=meta_data.get("disclaimer", "Not medical advice. For emergencies, call local emergency services."),
            when_to_call_emergency=meta_data.get("when_to_call_emergency")
        )
    
    def _parse_structured_text(
        self, 
        text: str, 
        context_parts: Optional[List[Dict[str, Any]]] = None
    ) -> ChecklistResponse:
        """
        Parse structured text response as fallback.
        
        Args:
            text: Structured text response
            context_parts: Optional context for citations
            
        Returns:
            ChecklistResponse object
        """
        # This is a simplified fallback parser
        # In practice, you'd implement more sophisticated text parsing
        
        steps = []
        lines = text.split('\n')
        
        current_step = None
        step_counter = 1
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for step indicators
            if any(indicator in line.lower() for indicator in ['step', 'action', '1.', '2.', '3.']):
                if current_step:
                    steps.append(current_step)
                
                current_step = ChecklistStep(
                    title=f"Step {step_counter}",
                    action=line,
                    source=self._infer_source_from_context(context_parts) if context_parts else None
                )
                step_counter += 1
            elif current_step and line:
                # Add to current step action
                current_step.action += " " + line
        
        # Add final step
        if current_step:
            steps.append(current_step)
        
        # If no steps found, create a single step
        if not steps:
            steps.append(ChecklistStep(
                title="Emergency Response",
                action=text[:500] + "..." if len(text) > 500 else text,
                source=self._infer_source_from_context(context_parts) if context_parts else None
            ))
        
        return ChecklistResponse(checklist=steps)
    
    def _infer_source_from_context(self, context_parts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Infer source citation from context parts.
        
        Args:
            context_parts: List of context parts with source info
            
        Returns:
            Source citation dictionary
        """
        if not context_parts:
            return None
            
        # Use the first context part as source
        context = context_parts[0]
        return {
            "doc_id": context["doc_id"],
            "loc": [
                context["location"]["start_offset"],
                context["location"]["end_offset"]
            ]
        }
    
    def _create_error_response(self, error_message: str) -> ChecklistResponse:
        """
        Create an error response.
        
        Args:
            error_message: Error message to include
            
        Returns:
            ChecklistResponse with error information
        """
        error_step = ChecklistStep(
            title="System Error",
            action=f"An error occurred while processing your request: {error_message}. Please try rephrasing your question or contact emergency services if this is urgent.",
            caution="If this is a life-threatening emergency, call your local emergency services immediately."
        )
        
        return ChecklistResponse(
            checklist=[error_step],
            disclaimer="System error occurred. For emergencies, call local emergency services immediately.",
            when_to_call_emergency="For any life-threatening emergency, call local emergency services immediately."
        )
    
    def close(self):
        """Clean up resources."""
        if hasattr(self.browser_tool, 'close'):
            self.browser_tool.close()