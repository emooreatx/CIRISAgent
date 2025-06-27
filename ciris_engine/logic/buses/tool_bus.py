"""
Tool message bus - handles all tool service operations
"""

import logging
import uuid
from typing import TYPE_CHECKING, List, Optional

from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.adapters.tools import ToolResult, ToolExecutionStatus, ToolInfo, ToolExecutionResult
from ciris_engine.protocols.services import ToolService
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from .base_bus import BaseBus, BusMessage

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry

logger = logging.getLogger(__name__)

class ToolBus(BaseBus[ToolService]):
    """
    Message bus for all tool operations.
    
    Handles:
    - execute_tool (returns ToolExecutionResult)
    - get_available_tools
    - get_tool_result (returns ToolExecutionResult)
    - get_tool_info
    - get_all_tool_info
    - validate_parameters
    """
    
    def __init__(self, service_registry: "ServiceRegistry", time_service: TimeServiceProtocol):
        super().__init__(
            service_type=ServiceType.TOOL,
            service_registry=service_registry
        )
        self._time_service = time_service
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: dict,
        handler_name: str = "default"
    ) -> ToolExecutionResult:
        """Execute a tool and return the result"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["execute_tool"]
        )
        
        if not service:
            logger.error(f"No tool service available for {handler_name}")
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.NOT_FOUND,
                success=False,
                data=None,
                error="No tool service available",
                correlation_id=str(uuid.uuid4())
            )
            
        try:
            result = await service.execute_tool(tool_name, parameters)
            # Protocol now returns ToolExecutionResult
            return result
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name}: {e}", exc_info=True)
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                success=False,
                data=None,
                error=str(e),
                correlation_id=str(uuid.uuid4())
            )
    
    async def get_available_tools(
        self,
        handler_name: str = "default"
    ) -> List[str]:
        """Get list of available tool names"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["get_available_tools"]
        )
        
        if not service:
            logger.error(f"No tool service available for {handler_name}")
            return []
            
        try:
            return await service.get_available_tools()
        except Exception as e:
            logger.error(f"Error getting available tools: {e}", exc_info=True)
            return []
    
    async def get_tool_result(
        self,
        correlation_id: str,
        timeout: float = 30.0,
        handler_name: str = "default"
    ) -> Optional[ToolExecutionResult]:
        """Get result of an async tool execution by correlation ID"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["get_tool_result"]
        )
        
        if not service:
            logger.error(f"No tool service available for {handler_name}")
            return None
            
        try:
            return await service.get_tool_result(correlation_id, timeout)
        except Exception as e:
            logger.error(f"Error getting tool result: {e}", exc_info=True)
            return None
    
    async def validate_parameters(
        self,
        tool_name: str,
        parameters: dict,
        handler_name: str = "default"
    ) -> bool:
        """Validate parameters for a tool"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["validate_parameters"]
        )
        
        if not service:
            logger.error(f"No tool service available for {handler_name}")
            return False
            
        try:
            return await service.validate_parameters(tool_name, parameters)
        except Exception as e:
            logger.error(f"Error validating parameters: {e}", exc_info=True)
            return False
    
    async def is_healthy(self, handler_name: str = "default") -> bool:
        """Check if tool service is healthy"""
        service = await self.get_service(handler_name=handler_name)
        if not service:
            return False
        try:
            return await service.is_healthy()
        except Exception as e:
            logger.error(f"Failed to check health: {e}")
            return False
    
    async def get_tool_info(
        self,
        tool_name: str,
        handler_name: str = "default"
    ) -> Optional[ToolInfo]:
        """Get detailed information about a specific tool"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["get_tool_info"]
        )
        
        if not service:
            logger.error(f"No tool service available for {handler_name}")
            return None
            
        try:
            return await service.get_tool_info(tool_name)
        except Exception as e:
            logger.error(f"Error getting tool info: {e}", exc_info=True)
            return None
    
    async def get_all_tool_info(
        self,
        handler_name: str = "default"
    ) -> List[ToolInfo]:
        """Get detailed information about all available tools"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["get_all_tool_info"]
        )
        
        if not service:
            logger.error(f"No tool service available for {handler_name}")
            return []
            
        try:
            return await service.get_all_tool_info()
        except Exception as e:
            logger.error(f"Error getting all tool info: {e}", exc_info=True)
            return []
    
    async def get_capabilities(self, handler_name: str = "default") -> List[str]:
        """Get tool service capabilities"""
        service = await self.get_service(handler_name=handler_name)
        if not service:
            return []
        try:
            return await service.get_capabilities()
        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return []
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process a tool message - currently all tool operations are synchronous"""
        logger.warning(f"Tool operations should be synchronous, got queued message: {type(message)}")