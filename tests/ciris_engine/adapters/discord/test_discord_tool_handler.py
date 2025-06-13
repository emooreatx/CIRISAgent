"""Tests for the Discord tool handler component."""
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from ciris_engine.adapters.discord.discord_tool_handler import DiscordToolHandler


class TestDiscordToolHandler:
    """Test the DiscordToolHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a tool handler instance."""
        return DiscordToolHandler()

    @pytest.fixture
    def mock_client(self):
        """Create a mock Discord client."""
        client = MagicMock(spec=discord.Client)
        return client

    @pytest.fixture
    def mock_tool_registry(self):
        """Create a mock tool registry."""
        registry = MagicMock()
        registry.tools = {"test_tool": MagicMock(), "another_tool": MagicMock()}
        registry.get_handler = MagicMock()
        registry.get_schema = MagicMock()
        return registry

    @pytest.fixture
    def mock_tool_handler(self):
        """Create a mock tool handler function."""
        async def tool_handler(args):
            return {"result": "success", "data": args.get("input", "default")}
        return tool_handler

    def test_initialization(self, handler):
        """Test handler initialization."""
        assert handler.tool_registry is None
        assert handler.client is None
        assert handler._tool_results == {}

    def test_initialization_with_params(self, mock_tool_registry, mock_client):
        """Test handler initialization with parameters."""
        handler = DiscordToolHandler(mock_tool_registry, mock_client)
        assert handler.tool_registry == mock_tool_registry
        assert handler.client == mock_client

    def test_set_client(self, handler, mock_client):
        """Test setting the Discord client."""
        handler.set_client(mock_client)
        assert handler.client == mock_client

    def test_set_tool_registry(self, handler, mock_tool_registry):
        """Test setting the tool registry."""
        handler.set_tool_registry(mock_tool_registry)
        assert handler.tool_registry == mock_tool_registry

    @pytest.mark.asyncio
    async def test_execute_tool_no_registry(self, handler):
        """Test executing tool without registry raises error."""
        with pytest.raises(RuntimeError, match="Tool registry not configured"):
            await handler.execute_tool("test_tool", {"input": "test"})

    @pytest.mark.asyncio
    async def test_execute_tool_no_handler(self, handler, mock_tool_registry):
        """Test executing non-existent tool raises error."""
        handler.set_tool_registry(mock_tool_registry)
        mock_tool_registry.get_handler.return_value = None
        
        with pytest.raises(RuntimeError, match="Tool handler for 'missing_tool' not found"):
            await handler.execute_tool("missing_tool", {"input": "test"})

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, handler, mock_tool_registry, mock_client, mock_tool_handler):
        """Test successful tool execution."""
        handler.set_tool_registry(mock_tool_registry)
        handler.set_client(mock_client)
        mock_tool_registry.get_handler.return_value = mock_tool_handler
        
        with patch('ciris_engine.adapters.discord.discord_tool_handler.persistence') as mock_persistence:
            result = await handler.execute_tool("test_tool", {"input": "test_data"})
            
            assert result["result"] == "success"
            assert result["data"] == "test_data"
            
            # Check that correlations were recorded
            mock_persistence.add_correlation.assert_called_once()
            mock_persistence.update_correlation.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_with_correlation_id(self, handler, mock_tool_registry, mock_client, mock_tool_handler):
        """Test tool execution with provided correlation ID."""
        handler.set_tool_registry(mock_tool_registry)
        handler.set_client(mock_client)
        mock_tool_registry.get_handler.return_value = mock_tool_handler
        
        correlation_id = "test_correlation_123"
        tool_args = {"input": "test_data", "correlation_id": correlation_id}
        
        with patch('ciris_engine.adapters.discord.discord_tool_handler.persistence'):
            result = await handler.execute_tool("test_tool", tool_args)
            
            # Result should be cached with the provided correlation ID
            assert correlation_id in handler._tool_results

    @pytest.mark.asyncio
    async def test_execute_tool_non_dict_result(self, handler, mock_tool_registry, mock_client):
        """Test tool execution with non-dict result."""
        handler.set_tool_registry(mock_tool_registry)
        handler.set_client(mock_client)
        
        # Mock tool that returns an object with __dict__
        class ToolResult:
            def __init__(self):
                self.status = "success"
                self.value = 42
        
        async def tool_handler(args):
            return ToolResult()
        
        mock_tool_registry.get_handler.return_value = tool_handler
        
        with patch('ciris_engine.adapters.discord.discord_tool_handler.persistence'):
            result = await handler.execute_tool("test_tool", {"input": "test"})
            
            assert isinstance(result, dict)
            assert "status" in result
            assert "value" in result

    @pytest.mark.asyncio
    async def test_execute_tool_failure(self, handler, mock_tool_registry, mock_client):
        """Test tool execution failure handling."""
        handler.set_tool_registry(mock_tool_registry)
        handler.set_client(mock_client)
        
        async def failing_tool_handler(args):
            raise ValueError("Tool execution failed")
        
        mock_tool_registry.get_handler.return_value = failing_tool_handler
        
        with patch('ciris_engine.adapters.discord.discord_tool_handler.persistence') as mock_persistence:
            with pytest.raises(ValueError, match="Tool execution failed"):
                await handler.execute_tool("test_tool", {"input": "test"})
            
            # Should still record failure in correlation
            mock_persistence.update_correlation.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tool_result_success(self, handler):
        """Test successful tool result retrieval."""
        correlation_id = "test_correlation_123"
        expected_result = {"status": "success", "data": "test"}
        
        # Manually add result to cache
        handler._tool_results[correlation_id] = expected_result
        
        result = await handler.get_tool_result(correlation_id, timeout=1)
        
        assert result == expected_result
        # Result should be removed from cache after retrieval
        assert correlation_id not in handler._tool_results

    @pytest.mark.asyncio
    async def test_get_tool_result_timeout(self, handler):
        """Test tool result retrieval timeout."""
        correlation_id = "missing_correlation_123"
        
        result = await handler.get_tool_result(correlation_id, timeout=1)
        
        assert result == {"correlation_id": correlation_id, "status": "not_found"}

    @pytest.mark.asyncio
    async def test_get_available_tools_no_registry(self, handler):
        """Test getting available tools without registry."""
        tools = await handler.get_available_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_get_available_tools_with_tools_attribute(self, handler, mock_tool_registry):
        """Test getting available tools with tools attribute."""
        handler.set_tool_registry(mock_tool_registry)
        mock_tool_registry.tools = {"tool1": MagicMock(), "tool2": MagicMock()}
        
        tools = await handler.get_available_tools()
        assert set(tools) == {"tool1", "tool2"}

    @pytest.mark.asyncio
    async def test_get_available_tools_with_get_tools_method(self, handler):
        """Test getting available tools with get_tools method."""
        mock_registry = MagicMock()
        mock_registry.get_tools.return_value = {"tool1": MagicMock(), "tool2": MagicMock()}
        # Remove tools attribute to test get_tools fallback
        if hasattr(mock_registry, 'tools'):
            delattr(mock_registry, 'tools')
        
        handler.set_tool_registry(mock_registry)
        
        tools = await handler.get_available_tools()
        assert set(tools) == {"tool1", "tool2"}

    @pytest.mark.asyncio
    async def test_get_available_tools_unknown_interface(self, handler):
        """Test getting available tools with unknown registry interface."""
        mock_registry = MagicMock()
        # Remove both tools and get_tools
        if hasattr(mock_registry, 'tools'):
            delattr(mock_registry, 'tools')
        if hasattr(mock_registry, 'get_tools'):
            delattr(mock_registry, 'get_tools')
        
        handler.set_tool_registry(mock_registry)
        
        tools = await handler.get_available_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_validate_tool_parameters_no_registry(self, handler):
        """Test parameter validation without registry."""
        result = await handler.validate_tool_parameters("test_tool", {"param": "value"})
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_tool_parameters_no_schema(self, handler, mock_tool_registry):
        """Test parameter validation without schema."""
        handler.set_tool_registry(mock_tool_registry)
        mock_tool_registry.get_schema.return_value = None
        
        result = await handler.validate_tool_parameters("test_tool", {"param": "value"})
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_tool_parameters_success(self, handler, mock_tool_registry):
        """Test successful parameter validation."""
        handler.set_tool_registry(mock_tool_registry)
        mock_tool_registry.get_schema.return_value = {"param1": "string", "param2": "int"}
        
        parameters = {"param1": "value", "param2": 42}
        result = await handler.validate_tool_parameters("test_tool", parameters)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_tool_parameters_missing_params(self, handler, mock_tool_registry):
        """Test parameter validation with missing parameters."""
        handler.set_tool_registry(mock_tool_registry)
        mock_tool_registry.get_schema.return_value = {"param1": "string", "param2": "int"}
        
        parameters = {"param1": "value"}  # Missing param2
        result = await handler.validate_tool_parameters("test_tool", parameters)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_tool_parameters_exception(self, handler, mock_tool_registry):
        """Test parameter validation with exception."""
        handler.set_tool_registry(mock_tool_registry)
        mock_tool_registry.get_schema.side_effect = Exception("Schema error")
        
        result = await handler.validate_tool_parameters("test_tool", {"param": "value"})
        assert result is False

    def test_clear_tool_results(self, handler):
        """Test clearing tool results cache."""
        # Add some results
        handler._tool_results["id1"] = {"result": "data1"}
        handler._tool_results["id2"] = {"result": "data2"}
        
        handler.clear_tool_results()
        
        assert handler._tool_results == {}

    def test_get_cached_result_count(self, handler):
        """Test getting cached result count."""
        assert handler.get_cached_result_count() == 0
        
        handler._tool_results["id1"] = {"result": "data1"}
        handler._tool_results["id2"] = {"result": "data2"}
        
        assert handler.get_cached_result_count() == 2

    def test_remove_cached_result_success(self, handler):
        """Test successful cached result removal."""
        correlation_id = "test_id"
        handler._tool_results[correlation_id] = {"result": "data"}
        
        result = handler.remove_cached_result(correlation_id)
        
        assert result is True
        assert correlation_id not in handler._tool_results

    def test_remove_cached_result_not_found(self, handler):
        """Test cached result removal when not found."""
        result = handler.remove_cached_result("missing_id")
        assert result is False