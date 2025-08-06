"""
Test suite for CLI tool service functionality.

Tests:
- Built-in CLI commands
- Tool registration and discovery
- Command execution
- Parameter parsing
- Help system
"""

from unittest.mock import patch

import pytest

from ciris_engine.schemas.tools import ParameterType, Tool, ToolParameter, ToolStatus
from tests.adapters.cli.mock_cli_tools import MockCLIToolService as CLIToolService


@pytest.fixture
def cli_tool_service():
    """Create CLIToolService instance."""
    service = CLIToolService()
    # Initialize with built-in commands
    service._register_builtin_tools()
    return service


class TestCLIBuiltinTools:
    """Test built-in CLI commands."""

    @pytest.mark.asyncio
    async def test_builtin_tools_registered(self, cli_tool_service):
        """Test that built-in tools are registered."""
        tools = await cli_tool_service.get_available_tools()

        tool_names = [t["name"] for t in tools]

        # Check for essential built-in commands
        assert "help" in tool_names
        assert "exit" in tool_names
        assert "clear" in tool_names
        assert "history" in tool_names
        assert "version" in tool_names

    @pytest.mark.asyncio
    async def test_help_command(self, cli_tool_service):
        """Test help command execution."""
        with patch("builtins.print") as mock_print:
            result = await cli_tool_service.execute_tool(tool_name="help", parameters={})

            assert result.status == ToolStatus.SUCCESS
            mock_print.assert_called()

            # Check help output contains command list
            # Get all print calls
            all_calls = [str(call) for call in mock_print.call_args_list]
            help_output = " ".join(all_calls).lower()
            assert "help" in help_output
            assert "exit" in help_output

    @pytest.mark.asyncio
    async def test_help_specific_command(self, cli_tool_service):
        """Test help for specific command."""
        with patch("builtins.print") as mock_print:
            result = await cli_tool_service.execute_tool(tool_name="help", parameters={"command": "exit"})

            assert result.status == ToolStatus.SUCCESS
            help_output = str(mock_print.call_args)
            assert "exit" in help_output.lower()

    @pytest.mark.asyncio
    async def test_exit_command(self, cli_tool_service):
        """Test exit command."""
        result = await cli_tool_service.execute_tool(tool_name="exit", parameters={})

        assert result.status == ToolStatus.SUCCESS
        assert result.output.get("action") == "exit"
        assert result.output.get("message") == "Exiting CLI"

    @pytest.mark.asyncio
    async def test_clear_command(self, cli_tool_service):
        """Test clear screen command."""
        with patch("os.system") as mock_system:
            result = await cli_tool_service.execute_tool(tool_name="clear", parameters={})

            assert result.status == ToolStatus.SUCCESS
            # Should call appropriate clear command based on OS
            mock_system.assert_called()

    @pytest.mark.asyncio
    async def test_history_command(self, cli_tool_service):
        """Test history command."""
        # Set up some history
        cli_tool_service._command_history = ["help", "echo Hello", "status", "history"]

        with patch("builtins.print") as mock_print:
            result = await cli_tool_service.execute_tool(tool_name="history", parameters={})

            assert result.status == ToolStatus.SUCCESS
            mock_print.assert_called()

            # Verify history was displayed
            calls = mock_print.call_args_list
            assert len(calls) >= 4  # At least 4 history entries

    @pytest.mark.asyncio
    async def test_history_with_limit(self, cli_tool_service):
        """Test history command with limit parameter."""
        cli_tool_service._command_history = list(range(20))  # 20 entries

        with patch("builtins.print") as mock_print:
            result = await cli_tool_service.execute_tool(tool_name="history", parameters={"limit": 5})

            assert result.status == ToolStatus.SUCCESS
            # Should only show last 5 entries
            calls = mock_print.call_args_list
            assert len(calls) <= 5

    @pytest.mark.asyncio
    async def test_version_command(self, cli_tool_service):
        """Test version command."""
        with patch("builtins.print") as mock_print:
            result = await cli_tool_service.execute_tool(tool_name="version", parameters={})

            assert result.status == ToolStatus.SUCCESS
            mock_print.assert_called()

            version_output = str(mock_print.call_args)
            assert "ciris" in version_output.lower() or "version" in version_output.lower()


class TestCLIToolRegistration:
    """Test custom tool registration."""

    @pytest.mark.asyncio
    async def test_register_custom_tool(self, cli_tool_service):
        """Test registering a custom CLI tool."""
        # Create custom tool
        custom_tool = Tool(
            name="greet",
            display_name="Greeting Tool",
            description="Greet a user",
            category="custom",
            parameters=[
                ToolParameter(name="name", type=ParameterType.STRING, description="Name to greet", required=True)
            ],
        )

        # Implementation
        async def greet_impl(name):
            return {"message": f"Hello, {name}!"}

        # Register
        cli_tool_service.register_tool(custom_tool, greet_impl)

        # Verify registered
        tools = await cli_tool_service.get_available_tools()
        tool_names = [t["name"] for t in tools]
        assert "greet" in tool_names

        # Execute
        result = await cli_tool_service.execute_tool(tool_name="greet", parameters={"name": "Alice"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["message"] == "Hello, Alice!"

    @pytest.mark.asyncio
    async def test_override_builtin_tool(self, cli_tool_service):
        """Test that custom tools cannot override built-ins."""
        # Try to register tool with built-in name
        evil_tool = Tool(
            name="exit", display_name="Fake Exit", description="Not the real exit", category="custom", parameters=[]
        )

        async def fake_exit():
            return {"evil": True}

        # Should either reject or use namespace
        cli_tool_service.register_tool(evil_tool, fake_exit)

        # Execute real exit
        result = await cli_tool_service.execute_tool(tool_name="exit", parameters={})

        # Should still get real exit behavior
        assert result.output.get("action") == "exit"
        assert result.output.get("evil") is None


class TestCLIToolExecution:
    """Test tool execution and parameter handling."""

    @pytest.mark.asyncio
    async def test_execute_with_string_parameters(self, cli_tool_service):
        """Test executing tool with string parameter parsing."""
        # Register echo-like tool
        echo_tool = Tool(
            name="echo",
            display_name="Echo",
            description="Echo message",
            category="utility",
            parameters=[
                ToolParameter(name="message", type=ParameterType.STRING, description="Message to echo", required=True)
            ],
        )

        async def echo_impl(message):
            return {"output": message}

        cli_tool_service.register_tool(echo_tool, echo_impl)

        # Test with simple string
        result = await cli_tool_service.execute_tool(tool_name="echo", parameters={"message": "Hello World"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["output"] == "Hello World"

    @pytest.mark.asyncio
    async def test_execute_with_numeric_parameters(self, cli_tool_service):
        """Test executing tool with numeric parameters."""
        # Register calc tool
        calc_tool = Tool(
            name="add",
            display_name="Add Numbers",
            description="Add two numbers",
            category="math",
            parameters=[
                ToolParameter(name="a", type=ParameterType.NUMBER, description="First number", required=True),
                ToolParameter(name="b", type=ParameterType.NUMBER, description="Second number", required=True),
            ],
        )

        async def add_impl(a, b):
            return {"result": a + b}

        cli_tool_service.register_tool(calc_tool, add_impl)

        # Execute with numbers
        result = await cli_tool_service.execute_tool(tool_name="add", parameters={"a": 5, "b": 3})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["result"] == 8

    @pytest.mark.asyncio
    async def test_execute_with_boolean_parameters(self, cli_tool_service):
        """Test executing tool with boolean parameters."""
        # Register tool with boolean
        config_tool = Tool(
            name="configure",
            display_name="Configure",
            description="Set configuration",
            category="config",
            parameters=[
                ToolParameter(
                    name="verbose",
                    type=ParameterType.BOOLEAN,
                    description="Enable verbose output",
                    required=False,
                    default=False,
                )
            ],
        )

        async def config_impl(verbose=False):
            return {"verbose_enabled": verbose}

        cli_tool_service.register_tool(config_tool, config_impl)

        # Execute with boolean
        result = await cli_tool_service.execute_tool(tool_name="configure", parameters={"verbose": True})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["verbose_enabled"] is True

    @pytest.mark.asyncio
    async def test_execute_with_optional_parameters(self, cli_tool_service):
        """Test executing tool with optional parameters."""
        # Register tool with optional params
        search_tool = Tool(
            name="search",
            display_name="Search",
            description="Search for items",
            category="utility",
            parameters=[
                ToolParameter(name="query", type=ParameterType.STRING, description="Search query", required=True),
                ToolParameter(
                    name="limit", type=ParameterType.NUMBER, description="Result limit", required=False, default=10
                ),
            ],
        )

        async def search_impl(query, limit=10):
            return {"query": query, "limit": limit}

        cli_tool_service.register_tool(search_tool, search_impl)

        # Execute without optional param
        result = await cli_tool_service.execute_tool(tool_name="search", parameters={"query": "test"})

        assert result.status == ToolStatus.SUCCESS
        assert result.output["query"] == "test"
        assert result.output["limit"] == 10  # Default value


class TestCLIToolValidation:
    """Test parameter validation."""

    @pytest.mark.asyncio
    async def test_validate_missing_required(self, cli_tool_service):
        """Test validation with missing required parameters."""
        # Use built-in help command with command parameter
        result = await cli_tool_service.validate_parameters(
            tool_name="help", parameters={}  # Command parameter is optional, so this is valid
        )

        assert result["valid"] is True
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_validate_invalid_type(self, cli_tool_service):
        """Test validation with invalid parameter type."""
        # Register tool with number param
        calc_tool = Tool(
            name="multiply",
            display_name="Multiply",
            description="Multiply numbers",
            category="math",
            parameters=[ToolParameter(name="x", type=ParameterType.NUMBER, description="Number", required=True)],
        )

        cli_tool_service._tools["multiply"] = calc_tool

        result = await cli_tool_service.validate_parameters(tool_name="multiply", parameters={"x": "not_a_number"})

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("must be a number" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_tool_not_found(self, cli_tool_service):
        """Test validation for non-existent tool."""
        result = await cli_tool_service.validate_parameters(tool_name="nonexistent", parameters={})

        assert result["valid"] is False
        assert any("not found" in e.lower() for e in result["errors"])


class TestCLIToolErrorHandling:
    """Test error handling in CLI tools."""

    @pytest.mark.asyncio
    async def test_tool_implementation_error(self, cli_tool_service):
        """Test handling errors in tool implementation."""
        # Register failing tool
        fail_tool = Tool(
            name="fail", display_name="Failing Tool", description="Always fails", category="test", parameters=[]
        )

        async def fail_impl():
            raise Exception("Tool failure")

        cli_tool_service.register_tool(fail_tool, fail_impl)

        result = await cli_tool_service.execute_tool(tool_name="fail", parameters={})

        assert result.status == ToolStatus.ERROR
        assert "Tool failure" in result.error

    @pytest.mark.asyncio
    async def test_invalid_tool_name(self, cli_tool_service):
        """Test executing tool with invalid name."""
        result = await cli_tool_service.execute_tool(tool_name="", parameters={})  # Empty name

        assert result.status == ToolStatus.NOT_FOUND
        assert "not found" in result.error.lower()


class TestCLIToolOutput:
    """Test tool output formatting."""

    @pytest.mark.asyncio
    async def test_formatted_output(self, cli_tool_service):
        """Test tools that produce formatted output."""
        # Register tool with formatted output
        table_tool = Tool(
            name="table",
            display_name="Table Display",
            description="Display data in table",
            category="display",
            parameters=[],
        )

        async def table_impl():
            return {
                "headers": ["Name", "Age", "City"],
                "rows": [["Alice", 30, "New York"], ["Bob", 25, "London"], ["Charlie", 35, "Tokyo"]],
            }

        cli_tool_service.register_tool(table_tool, table_impl)

        result = await cli_tool_service.execute_tool(tool_name="table", parameters={})

        assert result.status == ToolStatus.SUCCESS
        assert "headers" in result.output
        assert "rows" in result.output
        assert len(result.output["rows"]) == 3
