"""Tests for browser tool configuration."""

from campfire.harmony.browser_tool import create_browser_tool_config
from campfire.harmony.types import ToolConfig, ToolDefinition


class TestBrowserTool:
    """Test cases for browser tool configuration."""
    
    def test_create_browser_tool_config(self):
        """Test browser tool configuration creation."""
        config = create_browser_tool_config()
        
        assert isinstance(config, ToolConfig)
        assert config.recipient_prefix == "browser"
        assert isinstance(config.definition, ToolDefinition)
        assert config.definition.name == "browser"
    
    def test_browser_tool_methods(self):
        """Test browser tool method definitions."""
        config = create_browser_tool_config()
        methods = config.definition.methods
        
        # Should have exactly 3 methods
        assert len(methods) == 3
        
        method_names = [method["name"] for method in methods]
        assert "search" in method_names
        assert "open" in method_names
        assert "find" in method_names
    
    def test_search_method_definition(self):
        """Test search method definition."""
        config = create_browser_tool_config()
        methods = {method["name"]: method for method in config.definition.methods}
        
        search_method = methods["search"]
        assert search_method["description"] == "Search the local document corpus for relevant information"
        
        # Check arguments
        args = search_method["args"]
        assert "q" in args
        assert args["q"]["type"] == "string"
        assert "k" in args
        assert args["k"]["type"] == "integer"
        assert args["k"]["default"] == 5
    
    def test_open_method_definition(self):
        """Test open method definition."""
        config = create_browser_tool_config()
        methods = {method["name"]: method for method in config.definition.methods}
        
        open_method = methods["open"]
        assert open_method["description"] == "Open and retrieve a specific text window from a document"
        
        # Check arguments
        args = open_method["args"]
        assert "doc_id" in args
        assert args["doc_id"]["type"] == "string"
        assert "start" in args
        assert args["start"]["type"] == "integer"
        assert "end" in args
        assert args["end"]["type"] == "integer"
    
    def test_find_method_definition(self):
        """Test find method definition."""
        config = create_browser_tool_config()
        methods = {method["name"]: method for method in config.definition.methods}
        
        find_method = methods["find"]
        assert find_method["description"] == "Find specific patterns within a document from a given position"
        
        # Check arguments
        args = find_method["args"]
        assert "doc_id" in args
        assert args["doc_id"]["type"] == "string"
        assert "pattern" in args
        assert args["pattern"]["type"] == "string"
        assert "after" in args
        assert args["after"]["type"] == "integer"
    
    def test_method_descriptions_present(self):
        """Test that all methods have descriptions."""
        config = create_browser_tool_config()
        
        for method in config.definition.methods:
            assert "description" in method
            assert len(method["description"]) > 0
    
    def test_argument_descriptions_present(self):
        """Test that all method arguments have descriptions."""
        config = create_browser_tool_config()
        
        for method in config.definition.methods:
            if "args" in method:
                for arg_name, arg_def in method["args"].items():
                    assert "description" in arg_def
                    assert len(arg_def["description"]) > 0
                    assert "type" in arg_def