"""
Tool message bus - handles all tool service operations
"""

import logging
import uuid
from typing import TYPE_CHECKING, List, Optional

from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.adapters.tools import ToolExecutionStatus, ToolInfo, ToolExecutionResult
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
        logger.debug(f"execute_tool called with tool_name={tool_name}, parameters={parameters}")
        
        # Step 1: Get ALL tool services to find which ones support this tool
        all_tool_services = []
        try:
            # Access the registry's internal services dict to get all tool services
            from ciris_engine.schemas.runtime.enums import ServiceType
            
            # Use reflection to access the registry's internal structure
            # This is a temporary solution until we add a proper method
            if hasattr(self.service_registry, '_services'):
                tool_providers = self.service_registry._services.get(ServiceType.TOOL, [])
                for provider in tool_providers:
                    if hasattr(provider, 'instance') and hasattr(provider.instance, 'get_available_tools'):
                        all_tool_services.append(provider.instance)
                        
            logger.debug(f"Found {len(all_tool_services)} tool services")
        except Exception as e:
            logger.error(f"Failed to get all tool services: {e}")
            
        # If we couldn't get all services, fall back to getting at least one
        if not all_tool_services:
            service = await self.get_service(
                handler_name=handler_name,
                required_capabilities=["execute_tool"]
            )
            if service:
                all_tool_services = [service]
        
        # Step 2: Find which services support this specific tool
        supporting_services = []
        for service in all_tool_services:
            try:
                available_tools = await service.get_available_tools()
                logger.debug(f"Service {type(service).__name__} supports tools: {available_tools}")
                if tool_name in available_tools:
                    supporting_services.append(service)
            except Exception as e:
                logger.warning(f"Failed to get tools from {type(service).__name__}: {e}")
        
        # Step 3: If no service supports this tool, return NOT_FOUND
        if not supporting_services:
            logger.error(f"No service supports tool: {tool_name}")
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.NOT_FOUND,
                success=False,
                data=None,
                error=f"No service supports tool: {tool_name}",
                correlation_id=str(uuid.uuid4())
            )
        
        # Step 4: Select the appropriate service
        selected_service = None
        
        if len(supporting_services) == 1:
            # Only one service supports this tool
            selected_service = supporting_services[0]
            logger.debug(f"Using {type(selected_service).__name__} (only service with this tool)")
        else:
            # Multiple services support this tool - use routing logic
            # TODO: In future, extract channel_id/guild_id from context to route appropriately
            # For now, prefer APIToolService over SecretsToolService for general tools
            for service in supporting_services:
                if 'APIToolService' in type(service).__name__:
                    selected_service = service
                    break
            
            if not selected_service:
                selected_service = supporting_services[0]
            
            logger.debug(f"Selected {type(selected_service).__name__} from {len(supporting_services)} options")

        # Step 5: Execute the tool
        try:
            logger.debug(f"Executing tool '{tool_name}' with {type(selected_service).__name__}")
            result = await selected_service.execute_tool(tool_name, parameters)
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
