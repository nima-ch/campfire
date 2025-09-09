"""Browser tool configuration for local document search and retrieval."""

from .types import ToolConfig, ToolDefinition


def create_browser_tool_config() -> ToolConfig:
    """Create the browser tool configuration for local document corpus access.
    
    Returns:
        ToolConfig for the local browser tool
    """
    return ToolConfig(
        recipient_prefix="browser",
        definition=ToolDefinition(
            name="browser",
            methods=[
                {
                    "name": "search",
                    "description": "Search the local document corpus for relevant information",
                    "args": {
                        "q": {
                            "type": "string",
                            "description": "Search query for finding relevant documents"
                        },
                        "k": {
                            "type": "integer", 
                            "description": "Number of results to return (default: 5)",
                            "default": 5
                        }
                    }
                },
                {
                    "name": "open",
                    "description": "Open and retrieve a specific text window from a document",
                    "args": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document identifier from search results"
                        },
                        "start": {
                            "type": "integer",
                            "description": "Start position/offset in the document"
                        },
                        "end": {
                            "type": "integer", 
                            "description": "End position/offset in the document"
                        }
                    }
                },
                {
                    "name": "find",
                    "description": "Find specific patterns within a document from a given position",
                    "args": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document identifier to search within"
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Text pattern to search for"
                        },
                        "after": {
                            "type": "integer",
                            "description": "Position to start searching from"
                        }
                    }
                }
            ]
        )
    )