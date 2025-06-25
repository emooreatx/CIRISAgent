"""Tool Service Protocol."""

from typing import Protocol, Any, Dict, List, Optional
from abc import abstractmethod

from ...runtime.base import ServiceProtocol

class ToolServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for tool execution service."""
    
    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a tool."""
        ...
    
    @abstractmethod
    async def list_tools(self) -> List[str]:
        """List available tools."""
        ...
    
    @abstractmethod
    async def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool."""
        ...