"""
Core Tool Service: Provides system-wide tools that are always available to agents.
"""
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from ciris_engine.protocols.services import ToolService
from ciris_engine.adapters.tool_registry import ToolRegistry
from ciris_engine.adapters.core_tools import register_core_tools

logger = logging.getLogger(__name__)


class CoreToolService(ToolService):
    """
    Service that provides core system tools like SELF_HELP.
    These tools are always available regardless of which adapters are loaded.
    """
    
    def __init__(self) -> None:
        super().__init__()
        self.tool_registry = ToolRegistry()
        self._pending_results: Dict[str, Dict[str, Any]] = {}
        
        # Register core system tools
        register_core_tools(self.tool_registry)
        logger.info("CoreToolService initialized with core system tools")
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a core system tool."""
        handler = self.tool_registry.get_handler(tool_name)
        if not handler:
            return {
                "error": f"Core tool '{tool_name}' not found",
                "available_tools": await self.get_available_tools()
            }
        
        try:
            # Get correlation_id if provided
            correlation_id = parameters.pop("correlation_id", None)
            
            # Execute the tool
            result = await handler(parameters)
            
            # Convert ToolResult to dict
            result_dict = {
                "tool_name": result.tool_name,
                "status": result.execution_status.value,
                "result": result.result_data,
                "error": result.error_message
            }
            
            # Store result if correlation_id provided
            if correlation_id:
                self._pending_results[correlation_id] = result_dict
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Error executing core tool '{tool_name}': {e}")
            return {"error": str(e)}
    
    async def get_available_tools(self) -> List[str]:
        """Get list of available core tools."""
        return list(self.tool_registry._tools.keys())
    
    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Get result of a previously executed tool."""
        # For core tools, execution is synchronous, so result should be available immediately
        return self._pending_results.pop(correlation_id, None)
    
    async def validate_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """Validate parameters for a core tool."""
        return self.tool_registry.validate_arguments(tool_name, parameters)
    
    async def is_healthy(self) -> bool:
        """Health check - core tools are always healthy."""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return capabilities of this service."""
        return ["execute_tool", "get_available_tools", "validate_parameters", "get_tool_result"]
    
    async def start(self) -> None:
        """Start the service."""
        logger.info("CoreToolService started")
    
    async def stop(self) -> None:
        """Stop the service."""
        logger.info("CoreToolService stopped")