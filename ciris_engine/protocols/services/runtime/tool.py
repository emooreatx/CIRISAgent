"""Tool Service Protocol."""

from typing import Protocol, List, Optional
from abc import abstractmethod

from ...runtime.base import ServiceProtocol
from ciris_engine.schemas.adapters.tools import ToolExecutionResult, ToolInfo, ToolParameterSchema

class ToolServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for tool execution service."""

    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolExecutionResult:
        """Execute a tool with validated parameters.
        
        Note: parameters is a plain dict that has been validated against the tool's schema.
        The protocol accepts dict to allow flexibility in parameter types.
        """
        ...

    @abstractmethod
    async def list_tools(self) -> List[str]:
        """List available tools."""
        ...

    @abstractmethod
    async def get_tool_schema(self, tool_name: str) -> Optional[ToolParameterSchema]:
        """Get parameter schema for a specific tool."""
        ...
