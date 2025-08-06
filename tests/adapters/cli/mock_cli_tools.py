"""
Mock CLI Tool Service for testing.

This provides the interface expected by test_cli_tools.py.
"""

import os
import platform
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ciris_engine.schemas.tools import ParameterType, Tool, ToolParameter, ToolResult, ToolStatus


class MockCLIToolService:
    """Mock CLI tool service for testing."""

    def __init__(self):
        """Initialize the mock CLI tool service."""
        self._tools: Dict[str, Tool] = {}
        self._implementations: Dict[str, Callable] = {}
        self._command_history: List[str] = []
        self._results: Dict[str, ToolResult] = {}

    def _register_builtin_tools(self):
        """Register built-in CLI commands."""
        # Help command
        help_tool = Tool(
            name="help",
            display_name="Help",
            description="Show available commands",
            category="system",
            parameters=[
                ToolParameter(
                    name="command", type=ParameterType.STRING, description="Command to get help for", required=False
                )
            ],
        )
        self._tools["help"] = help_tool
        self._implementations["help"] = self._help_command

        # Exit command
        exit_tool = Tool(name="exit", display_name="Exit", description="Exit the CLI", category="system", parameters=[])
        self._tools["exit"] = exit_tool
        self._implementations["exit"] = self._exit_command

        # Clear command
        clear_tool = Tool(
            name="clear", display_name="Clear Screen", description="Clear the screen", category="system", parameters=[]
        )
        self._tools["clear"] = clear_tool
        self._implementations["clear"] = self._clear_command

        # History command
        history_tool = Tool(
            name="history",
            display_name="Command History",
            description="Show command history",
            category="system",
            parameters=[
                ToolParameter(
                    name="limit",
                    type=ParameterType.NUMBER,
                    description="Number of commands to show",
                    required=False,
                    default=10,
                )
            ],
        )
        self._tools["history"] = history_tool
        self._implementations["history"] = self._history_command

        # Version command
        version_tool = Tool(
            name="version", display_name="Version", description="Show CIRIS version", category="system", parameters=[]
        )
        self._tools["version"] = version_tool
        self._implementations["version"] = self._version_command

    async def _help_command(self, command: Optional[str] = None) -> Dict[str, Any]:
        """Execute help command."""
        if command:
            if command in self._tools:
                tool = self._tools[command]
                print(f"Help for {command}:")
                print(f"  {tool.description}")
                if tool.parameters:
                    print("  Parameters:")
                    for param in tool.parameters:
                        req = "required" if param.required else "optional"
                        print(f"    - {param.name} ({param.type.value}, {req}): {param.description}")
            else:
                print(f"Unknown command: {command}")
        else:
            print("Available commands:")
            for name, tool in self._tools.items():
                print(f"  {name} - {tool.description}")
        return {"displayed": True}

    async def _exit_command(self) -> Dict[str, Any]:
        """Execute exit command."""
        return {"action": "exit", "message": "Exiting CLI"}

    async def _clear_command(self) -> Dict[str, Any]:
        """Execute clear screen command."""
        # Clear screen based on OS
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")
        return {"cleared": True}

    async def _history_command(self, limit: int = 10) -> Dict[str, Any]:
        """Execute history command."""
        # Show last N commands
        history_to_show = self._command_history[-limit:] if limit > 0 else self._command_history
        for i, cmd in enumerate(history_to_show, 1):
            print(f"{i}. {cmd}")
        return {"displayed": len(history_to_show)}

    async def _version_command(self) -> Dict[str, Any]:
        """Execute version command."""
        print("CIRIS CLI Tool Service v1.0.0")
        return {"version": "1.0.0"}

    def register_tool(self, tool: Tool, implementation: Callable):
        """Register a custom tool."""
        # Don't allow overriding built-in tools
        if tool.name in ["help", "exit", "clear", "history", "version"]:
            # Register with namespace prefix
            namespaced_name = f"custom_{tool.name}"
            self._tools[namespaced_name] = tool
            self._implementations[namespaced_name] = implementation
        else:
            self._tools[tool.name] = tool
            self._implementations[tool.name] = implementation

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return [
            {
                "name": tool.name,
                "display_name": tool.display_name,
                "description": tool.description,
                "category": tool.category,
            }
            for tool in self._tools.values()
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a tool."""
        # Track command in history
        self._command_history.append(tool_name)

        if tool_name not in self._tools:
            return ToolResult(
                status=ToolStatus.NOT_FOUND, error=f"Tool not found: {tool_name}", timestamp=datetime.now()
            )

        tool = self._tools[tool_name]
        implementation = self._implementations[tool_name]

        try:
            # Validate parameters
            validation = await self.validate_parameters(tool_name, parameters)
            if not validation["valid"]:
                return ToolResult(
                    status=ToolStatus.ERROR, error="; ".join(validation["errors"]), timestamp=datetime.now()
                )

            # Build kwargs from parameters
            kwargs = {}
            for param in tool.parameters:
                if param.name in parameters:
                    kwargs[param.name] = parameters[param.name]
                elif param.default is not None:
                    kwargs[param.name] = param.default
                elif param.required:
                    # This shouldn't happen if validation passed
                    raise ValueError(f"Missing required parameter: {param.name}")

            # Execute the tool
            output = await implementation(**kwargs)

            return ToolResult(status=ToolStatus.SUCCESS, output=output, timestamp=datetime.now())

        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=str(e), timestamp=datetime.now())

    async def validate_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate tool parameters."""
        if tool_name not in self._tools:
            return {"valid": False, "errors": [f"Tool not found: {tool_name}"]}

        tool = self._tools[tool_name]
        errors = []

        # Check required parameters
        for param in tool.parameters:
            if param.required and param.name not in parameters:
                errors.append(f"Missing required parameter: {param.name}")

        # Check parameter types
        for param in tool.parameters:
            if param.name in parameters:
                value = parameters[param.name]
                if param.type == ParameterType.NUMBER:
                    if not isinstance(value, (int, float)):
                        errors.append(f"Parameter {param.name} must be a number")
                elif param.type == ParameterType.BOOLEAN:
                    if not isinstance(value, bool):
                        errors.append(f"Parameter {param.name} must be a boolean")
                elif param.type == ParameterType.STRING:
                    if not isinstance(value, str):
                        errors.append(f"Parameter {param.name} must be a string")

        return {"valid": len(errors) == 0, "errors": errors}
