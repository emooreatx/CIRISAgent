"""
Tool message bus - handles all tool service operations
"""

import logging
from typing import Optional, Dict, Any, List

from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.schemas.tool_schemas_v1 import ToolResult, ToolExecutionStatus
from ciris_engine.protocols.services import ToolService
from .base_bus import BaseBus, BusMessage

logger = logging.getLogger(__name__)


class ToolBus(BaseBus):
    """
    Message bus for all tool operations.
    
    Handles:
    - execute_tool
    - list_tools
    - get_tool_result
    """
    
    def __init__(self, service_registry: Any):
        super().__init__(
            service_type=ServiceType.TOOL,
            service_registry=service_registry
        )
    
    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        handler_name: str,
        correlation_id: Optional[str] = None
    ) -> ToolResult:
        """Execute a tool and return the result"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["execute_tool"]
        )
        
        if not service:
            logger.error(f"No tool service available for {handler_name}")
            return ToolResult(
                tool_name=tool_name,
                execution_status=ToolExecutionStatus.FAILED,
                result_data=None,
                error_message="No tool service available"
            )
            
        try:
            result = await service.execute_tool(tool_name, args)
            # Ensure we return a ToolResult
            if isinstance(result, ToolResult):
                return result
            # Convert dict or other format to ToolResult
            return ToolResult(
                tool_name=tool_name,
                execution_status=ToolExecutionStatus.SUCCESS,
                result_data={"result": result} if result is not None else None
            )
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name}: {e}", exc_info=True)
            return ToolResult(
                tool_name=tool_name,
                execution_status=ToolExecutionStatus.FAILED,
                result_data=None,
                error_message=str(e)
            )
    
    async def list_tools(
        self,
        handler_name: str = "system"
    ) -> Dict[str, Any]:
        """List all available tools across all tool services"""
        # Get all tool services
        all_tools = {}
        
        # This aggregates tools from all services
        # We'll use the registry to get all tool services
        try:
            # Get service from registry
            service = await self.get_service(
                handler_name=handler_name,
                required_capabilities=["get_available_tools"]
            )
            
            if service:
                tools = await service.get_available_tools()
                all_tools.update(tools)
            else:
                logger.warning("No tool service found")
                
        except Exception as e:
            logger.error(f"Error listing tools: {e}", exc_info=True)
            
        return all_tools
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process a tool message - currently all tool operations are synchronous"""
        logger.warning(f"Tool operations should be synchronous, got queued message: {type(message)}")