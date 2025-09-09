"""
Unit tests for the agent composition system.
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from campfire.harmony.agent import (
    AgentCompositionSystem,
    ChecklistStep,
    ChecklistResponse
)
from campfire.harmony.types import HarmonyMessage, HarmonyRole, ToolCall, ToolResult
from campfire.llm.base import LLMProvider


class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def __init__(self, supports_tokens: bool = True):
        self._supports_tokens = supports_tokens
        self.generate_calls = []
        self.mock_responses = []
        self.response_index = 0
    
    def supports_tokens(self) -> bool:
        return self._supports_tokens
    
    def generate(self, prefill_ids, stop_token_ids, max_tokens=2048, temperature=0.1):
        call_info = {
            "prefill_ids": prefill_ids,
            "stop_token_ids": stop_token_ids,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        self.generate_calls.append(call_info)
        
        if self.response_index < len(self.mock_responses):
            response = self.mock_responses[self.response_index]
            self.response_index += 1
            return response
        
        # Default response
        return {
            "completion_tokens": [1, 2, 3],
            "completion_text": "Mock response",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}
        }
    
    def is_available(self) -> bool:
        return True
    
    def get_model_info(self):
        return {"name": "mock-model", "provider": "mock"}
    
    def add_mock_response(self, response):
        """Add a mock response to be returned by generate()."""
        self.mock_responses.append(response)


@pytest.fixture
def mock_corpus_db():
    """Mock corpus database."""
    return "/tmp/test_corpus.db"


@pytest.fixture
def mock_browser_tool():
    """Mock browser tool."""
    with patch('campfire.harmony.agent.LocalBrowserTool') as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        
        # Default search response
        mock_instance.search.return_value = {
            "status": "success",
            "query": "test query",
            "total_results": 1,
            "results": [{
                "doc_id": "test_doc",
                "doc_title": "Test Document",
                "snippet": "Test snippet",
                "location": {
                    "start_offset": 100,
                    "end_offset": 200,
                    "page_number": 1
                },
                "relevance_score": 0.9
            }]
        }
        
        # Default open response
        mock_instance.open.return_value = {
            "status": "success",
            "doc_id": "test_doc",
            "doc_title": "Test Document",
            "text": "This is test content from the document.",
            "location": {
                "start_offset": 100,
                "end_offset": 200,
                "actual_start": 100,
                "actual_end": 200
            },
            "chunk_count": 1
        }
        
        # Default find response
        mock_instance.find.return_value = {
            "status": "success",
            "doc_id": "test_doc",
            "doc_title": "Test Document",
            "pattern": "test",
            "search_after": 0,
            "matches": [{
                "text": "test",
                "context": "This is a test context",
                "location": {
                    "start_offset": 150,
                    "end_offset": 154,
                    "page_number": 1
                }
            }],
            "total_matches": 1
        }
        
        yield mock_instance


class TestChecklistStep:
    """Test ChecklistStep class."""
    
    def test_basic_step_creation(self):
        """Test creating a basic checklist step."""
        step = ChecklistStep(
            title="Test Step",
            action="Do something"
        )
        
        assert step.title == "Test Step"
        assert step.action == "Do something"
        assert step.source is None
        assert step.caution is None
    
    def test_step_with_source_and_caution(self):
        """Test creating a step with source and caution."""
        source = {"doc_id": "test_doc", "loc": [100, 200]}
        step = ChecklistStep(
            title="Test Step",
            action="Do something",
            source=source,
            caution="Be careful"
        )
        
        assert step.source == source
        assert step.caution == "Be careful"
    
    def test_step_to_dict(self):
        """Test converting step to dictionary."""
        source = {"doc_id": "test_doc", "loc": [100, 200]}
        step = ChecklistStep(
            title="Test Step",
            action="Do something",
            source=source,
            caution="Be careful"
        )
        
        result = step.to_dict()
        expected = {
            "title": "Test Step",
            "action": "Do something",
            "source": source,
            "caution": "Be careful"
        }
        
        assert result == expected


class TestChecklistResponse:
    """Test ChecklistResponse class."""
    
    def test_basic_response_creation(self):
        """Test creating a basic checklist response."""
        steps = [
            ChecklistStep("Step 1", "Action 1"),
            ChecklistStep("Step 2", "Action 2")
        ]
        
        response = ChecklistResponse(checklist=steps)
        
        assert len(response.checklist) == 2
        assert response.disclaimer == "Not medical advice. For emergencies, call local emergency services."
        assert response.when_to_call_emergency is None
    
    def test_response_to_dict(self):
        """Test converting response to dictionary."""
        steps = [
            ChecklistStep("Step 1", "Action 1", source={"doc_id": "doc1", "loc": [0, 100]})
        ]
        
        response = ChecklistResponse(
            checklist=steps,
            disclaimer="Custom disclaimer",
            when_to_call_emergency="When in doubt"
        )
        
        result = response.to_dict()
        
        assert "checklist" in result
        assert "meta" in result
        assert len(result["checklist"]) == 1
        assert result["meta"]["disclaimer"] == "Custom disclaimer"
        assert result["meta"]["when_to_call_emergency"] == "When in doubt"


class TestAgentCompositionSystem:
    """Test AgentCompositionSystem class."""
    
    def test_initialization(self, mock_corpus_db, mock_browser_tool):
        """Test agent system initialization."""
        llm_provider = MockLLMProvider()
        
        agent = AgentCompositionSystem(
            llm_provider=llm_provider,
            corpus_db_path=mock_corpus_db
        )
        
        assert agent.llm_provider == llm_provider
        assert agent.corpus_db_path == mock_corpus_db
        assert agent.max_tool_iterations == 5
        assert agent.harmony_engine is not None
        assert agent.browser_tool is not None
    
    def test_tool_loop_mode_detection(self, mock_corpus_db, mock_browser_tool):
        """Test that tool-loop mode is used for providers that support tokens."""
        llm_provider = MockLLMProvider(supports_tokens=True)
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Mock the tool-loop processing method
        with patch.object(agent, '_process_with_tool_loop') as mock_tool_loop:
            mock_tool_loop.return_value = ChecklistResponse([])
            
            agent.process_query("test query")
            mock_tool_loop.assert_called_once_with("test query")
    
    def test_rag_fallback_mode_detection(self, mock_corpus_db, mock_browser_tool):
        """Test that RAG fallback mode is used for providers without token support."""
        llm_provider = MockLLMProvider(supports_tokens=False)
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Mock the RAG processing method
        with patch.object(agent, '_process_with_rag_fallback') as mock_rag:
            mock_rag.return_value = ChecklistResponse([])
            
            agent.process_query("test query")
            mock_rag.assert_called_once_with("test query")
    
    def test_tool_call_execution(self, mock_corpus_db, mock_browser_tool):
        """Test tool call execution."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Create test tool calls
        tool_calls = [
            ToolCall(
                recipient="browser",
                method="search",
                args={"q": "test query", "k": 3},
                call_id="call_1"
            ),
            ToolCall(
                recipient="browser",
                method="open",
                args={"doc_id": "test_doc", "start": 100, "end": 200},
                call_id="call_2"
            )
        ]
        
        results = agent._execute_tool_calls(tool_calls)
        
        assert len(results) == 2
        assert all(isinstance(result, ToolResult) for result in results)
        assert results[0].call_id == "call_1"
        assert results[1].call_id == "call_2"
        
        # Verify browser tool was called
        mock_browser_tool.search.assert_called_once_with(q="test query", k=3)
        mock_browser_tool.open.assert_called_once_with(doc_id="test_doc", start=100, end=200)
    
    def test_browser_tool_methods(self, mock_corpus_db, mock_browser_tool):
        """Test all browser tool methods."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Test search
        search_call = ToolCall(
            recipient="browser",
            method="search",
            args={"q": "bleeding", "k": 5}
        )
        result = agent._execute_browser_call(search_call)
        assert result["status"] == "success"
        mock_browser_tool.search.assert_called_with(q="bleeding", k=5)
        
        # Test open
        open_call = ToolCall(
            recipient="browser",
            method="open",
            args={"doc_id": "ifrc_doc", "start": 500, "end": 1000}
        )
        result = agent._execute_browser_call(open_call)
        assert result["status"] == "success"
        mock_browser_tool.open.assert_called_with(doc_id="ifrc_doc", start=500, end=1000)
        
        # Test find
        find_call = ToolCall(
            recipient="browser",
            method="find",
            args={"doc_id": "who_doc", "pattern": "first aid", "after": 200}
        )
        result = agent._execute_browser_call(find_call)
        assert result["status"] == "success"
        mock_browser_tool.find.assert_called_with(doc_id="who_doc", pattern="first aid", after=200)
    
    def test_unknown_tool_handling(self, mock_corpus_db, mock_browser_tool):
        """Test handling of unknown tools."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        unknown_call = ToolCall(
            recipient="unknown_tool",
            method="unknown_method",
            args={},
            call_id="unknown_call"
        )
        
        results = agent._execute_tool_calls([unknown_call])
        
        assert len(results) == 1
        assert results[0].error is not None
        assert "Unknown tool" in results[0].error
    
    def test_json_extraction_from_text(self, mock_corpus_db, mock_browser_tool):
        """Test JSON extraction from various text formats."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Test JSON in code block
        text_with_json_block = '''
        Here is the response:
        ```json
        {"checklist": [{"title": "Test", "action": "Do something"}]}
        ```
        '''
        
        json_str = agent._extract_json_from_text(text_with_json_block)
        assert json_str is not None
        data = json.loads(json_str)
        assert "checklist" in data
        
        # Test inline JSON
        text_with_inline_json = '''
        Response: {"checklist": [{"title": "Step 1", "action": "Action 1"}], "meta": {"disclaimer": "Test"}}
        '''
        
        json_str = agent._extract_json_from_text(text_with_inline_json)
        assert json_str is not None
        data = json.loads(json_str)
        assert "checklist" in data
        assert "meta" in data
    
    def test_checklist_creation_from_json(self, mock_corpus_db, mock_browser_tool):
        """Test creating checklist from JSON data."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        json_data = {
            "checklist": [
                {
                    "title": "Step 1",
                    "action": "First action",
                    "source": {"doc_id": "doc1", "loc": [0, 100]},
                    "caution": "Be careful"
                },
                {
                    "title": "Step 2", 
                    "action": "Second action"
                }
            ],
            "meta": {
                "disclaimer": "Custom disclaimer",
                "when_to_call_emergency": "When needed"
            }
        }
        
        response = agent._create_checklist_from_json(json_data)
        
        assert len(response.checklist) == 2
        assert response.checklist[0].title == "Step 1"
        assert response.checklist[0].source is not None
        assert response.checklist[0].caution == "Be careful"
        assert response.checklist[1].source is None
        assert response.disclaimer == "Custom disclaimer"
        assert response.when_to_call_emergency == "When needed"
    
    def test_rag_prompt_creation(self, mock_corpus_db, mock_browser_tool):
        """Test RAG prompt creation with context."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        context_parts = [
            {
                "doc_id": "ifrc_doc",
                "doc_title": "IFRC Guidelines",
                "text": "First aid procedures for bleeding...",
                "location": {"start_offset": 100, "end_offset": 200}
            },
            {
                "doc_id": "who_doc",
                "doc_title": "WHO Guidelines",
                "text": "Psychological first aid steps...",
                "location": {"start_offset": 300, "end_offset": 400}
            }
        ]
        
        prompt = agent._create_rag_prompt("How to stop bleeding?", context_parts)
        
        assert "How to stop bleeding?" in prompt
        assert "IFRC Guidelines" in prompt
        assert "WHO Guidelines" in prompt
        assert "First aid procedures" in prompt
        assert "Psychological first aid" in prompt
        assert "100-200" in prompt
        assert "300-400" in prompt
    
    def test_error_response_creation(self, mock_corpus_db, mock_browser_tool):
        """Test error response creation."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        error_response = agent._create_error_response("Test error message")
        
        assert len(error_response.checklist) == 1
        assert "Test error message" in error_response.checklist[0].action
        assert "System Error" in error_response.checklist[0].title
        assert error_response.checklist[0].caution is not None
        assert "emergency services" in error_response.disclaimer
    
    def test_structured_text_parsing(self, mock_corpus_db, mock_browser_tool):
        """Test parsing structured text as fallback."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        structured_text = """
        Step 1: Check for consciousness
        Tap the person's shoulders and shout "Are you okay?"
        
        Step 2: Call for help
        If no response, call emergency services immediately.
        
        Action 3: Check breathing
        Look for chest movement for 10 seconds.
        """
        
        response = agent._parse_structured_text(structured_text)
        
        assert len(response.checklist) >= 1
        assert any("consciousness" in step.action.lower() for step in response.checklist)
    
    @patch('campfire.harmony.agent.HarmonyEngine')
    def test_tool_loop_integration(self, mock_harmony_engine, mock_corpus_db, mock_browser_tool):
        """Test tool loop integration with Harmony engine."""
        # Setup mocks
        mock_engine_instance = Mock()
        mock_harmony_engine.return_value = mock_engine_instance
        
        mock_engine_instance.render_conversation.return_value = ([1, 2, 3], [4, 5])
        mock_engine_instance.parse_completion.return_value = ([], [])
        mock_engine_instance.conversation_history = [
            Mock(role=HarmonyRole.ASSISTANT, content='{"checklist": [{"title": "Test", "action": "Test action"}]}')
        ]
        
        llm_provider = MockLLMProvider(supports_tokens=True)
        llm_provider.add_mock_response({
            "completion_tokens": [10, 11, 12],
            "completion_text": "Test response",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6}
        })
        
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        agent.harmony_engine = mock_engine_instance
        
        # Test tool loop processing
        response = agent._process_with_tool_loop("test query")
        
        # Verify Harmony engine was used
        mock_engine_instance.clear_conversation.assert_called()
        mock_engine_instance.add_message.assert_called()
        mock_engine_instance.render_conversation.assert_called()
        
        # Verify LLM was called
        assert len(llm_provider.generate_calls) == 1
    
    def test_multi_hop_tool_calling(self, mock_corpus_db, mock_browser_tool):
        """Test multi-hop tool calling sequence (search → open → find)."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Simulate a sequence of tool calls
        tool_calls = [
            # First: search for information
            ToolCall(
                recipient="browser",
                method="search",
                args={"q": "bleeding control", "k": 3},
                call_id="search_1"
            ),
            # Second: open a specific document
            ToolCall(
                recipient="browser", 
                method="open",
                args={"doc_id": "ifrc_doc", "start": 500, "end": 1000},
                call_id="open_1"
            ),
            # Third: find specific pattern in the document
            ToolCall(
                recipient="browser",
                method="find", 
                args={"doc_id": "ifrc_doc", "pattern": "pressure point", "after": 500},
                call_id="find_1"
            )
        ]
        
        results = agent._execute_tool_calls(tool_calls)
        
        assert len(results) == 3
        assert all(result.error is None for result in results)
        
        # Verify the sequence was executed
        mock_browser_tool.search.assert_called_once()
        mock_browser_tool.open.assert_called_once()
        mock_browser_tool.find.assert_called_once()
    
    def test_error_handling_in_tool_execution(self, mock_corpus_db, mock_browser_tool):
        """Test error handling during tool execution."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Make browser tool raise an exception
        mock_browser_tool.search.side_effect = Exception("Database error")
        
        tool_call = ToolCall(
            recipient="browser",
            method="search",
            args={"q": "test"},
            call_id="error_call"
        )
        
        results = agent._execute_tool_calls([tool_call])
        
        assert len(results) == 1
        assert results[0].error is not None
        assert "Database error" in results[0].error
    
    def test_malformed_response_handling(self, mock_corpus_db, mock_browser_tool):
        """Test handling of malformed LLM responses."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Test with malformed JSON
        malformed_text = "This is not JSON at all, just plain text response."
        response = agent._parse_text_response(malformed_text)
        
        # Should create a fallback response
        assert len(response.checklist) >= 1
        assert "emergency services" in response.disclaimer.lower()
        
        # Test with partial JSON
        partial_json = '{"checklist": [{"title": "Incomplete'
        response = agent._parse_text_response(partial_json)
        
        # Should handle gracefully
        assert isinstance(response, ChecklistResponse)
    
    def test_resource_cleanup(self, mock_corpus_db, mock_browser_tool):
        """Test resource cleanup."""
        llm_provider = MockLLMProvider()
        agent = AgentCompositionSystem(llm_provider, mock_corpus_db)
        
        # Test cleanup
        agent.close()
        
        # Verify browser tool close was called
        mock_browser_tool.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])