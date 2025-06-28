"""Discord tool handling component for tool execution operations."""
import discord
import logging
import asyncio
import uuid
from typing import Dict, List, Optional, TYPE_CHECKING, Any
from datetime import datetime

from ciris_engine.schemas.telemetry.core import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine.schemas.persistence.core import CorrelationUpdateRequest
from ciris_engine.schemas.adapters.tools import ToolInfo, ToolParameterSchema, ToolExecutionResult, ToolExecutionStatus
from ciris_engine.logic import persistence

if TYPE_CHECKING:
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

class DiscordToolHandler:
    """Handles Discord tool execution and result management."""
    
    def __init__(self, tool_registry: Optional[Any] = None, client: Optional[discord.Client] = None, time_service: Optional["TimeServiceProtocol"] = None) -> None:
        """Initialize the tool handler.
        
        Args:
            tool_registry: Registry of available tools
            client: Discord client instance
            time_service: Time service for consistent time operations
        """
        self.tool_registry = tool_registry
        self.client = client
        self._tool_results: Dict[str, ToolExecutionResult] = {}
        self._time_service = time_service
        
        # Ensure we have a time service
        if self._time_service is None:
            from ciris_engine.logic.services.lifecycle.time import TimeService
            self._time_service = TimeService()
    
    def set_client(self, client: discord.Client) -> None:
        """Set the Discord client after initialization.
        
        Args:
            client: Discord client instance
        """
        self.client = client
    
    def set_tool_registry(self, tool_registry: Any) -> None:
        """Set the tool registry after initialization.
        
        Args:
            tool_registry: Registry of available tools
        """
        self.tool_registry = tool_registry
    
    async def execute_tool(self, tool_name: str, tool_args: dict) -> ToolExecutionResult:
        """Execute a registered Discord tool via the tool registry.
        
        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments to pass to the tool
            
        Returns:
            Tool execution result as a dictionary
            
        Raises:
            RuntimeError: If tool registry is not configured or tool not found
        """
        if not self.tool_registry:
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                success=False,
                data=None,
                error="Tool registry not configured",
                correlation_id=str(uuid.uuid4())
            )
        
        handler = self.tool_registry.get_handler(tool_name)
        if not handler:
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                success=False,
                data=None,
                error=f"Tool handler for '{tool_name}' not found",
                correlation_id=str(uuid.uuid4())
            )
        
        correlation_id = tool_args.get("correlation_id", str(uuid.uuid4()))
        
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=correlation_id,
                service_type="discord",
                handler_name="DiscordAdapter",
                action_type=tool_name,
                request_data=tool_args,
                status=ServiceCorrelationStatus.PENDING,
                created_at=self._time_service.now().isoformat(),
                updated_at=self._time_service.now().isoformat(),
            )
        )
        
        try:
            import time
            start_time = time.time()
            tool_args_with_bot = {**tool_args, "bot": self.client}
            result = await handler(tool_args_with_bot)
            execution_time = (time.time() - start_time) * 1000
            
            result_dict = result if isinstance(result, dict) else result.__dict__
            
            # Create ToolExecutionResult
            execution_result = ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.COMPLETED if result_dict.get("success", True) else ToolExecutionStatus.FAILED,
                success=result_dict.get("success", True),
                data=result_dict,
                error=result_dict.get("error"),
                correlation_id=correlation_id or str(uuid.uuid4())
            )
            
            if correlation_id:
                self._tool_results[correlation_id] = execution_result
                persistence.update_correlation(
                    CorrelationUpdateRequest(
                        correlation_id=correlation_id,
                        response_data=result_dict,
                        status=ServiceCorrelationStatus.COMPLETED,
                        metric_value=None,
                        tags=None
                    )
                )
            
            return execution_result
            
        except Exception as e:
            logger.exception(f"Tool execution failed for {tool_name}: {e}")
            error_result = {"error": str(e), "tool_name": tool_name}
            
            if correlation_id:
                persistence.update_correlation(
                    CorrelationUpdateRequest(
                        correlation_id=correlation_id,
                        response_data=error_result,
                        status=ServiceCorrelationStatus.FAILED,
                        metric_value=None,
                        tags=None
                    )
                )
            
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                success=False,
                data=None,
                error=str(e),
                correlation_id=correlation_id or str(uuid.uuid4())
            )
    
    async def get_tool_result(self, correlation_id: str, timeout: int = 10) -> Optional[ToolExecutionResult]:
        """Fetch a tool result by correlation ID from the internal cache.
        
        Args:
            correlation_id: The correlation ID of the tool execution
            timeout: Maximum time to wait for the result in seconds
            
        Returns:
            Tool result dictionary or not_found status
        """
        for _ in range(timeout * 10):  # Check every 0.1 seconds
            if correlation_id in self._tool_results:
                return self._tool_results.pop(correlation_id)
            await asyncio.sleep(0.1)
        
        logger.warning(f"Tool result for correlation_id {correlation_id} not found after {timeout}s")
        return None
    
    async def get_available_tools(self) -> List[str]:
        """Return names of registered Discord tools.
        
        Returns:
            List of available tool names
        """
        if not self.tool_registry:
            return []
        
        if hasattr(self.tool_registry, 'tools'):
            return list(self.tool_registry.tools.keys())
        elif hasattr(self.tool_registry, 'get_tools'):
            return list(self.tool_registry.get_tools().keys())
        else:
            logger.warning("Tool registry interface not recognized")
            return []
    
    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """Get detailed information about a specific tool."""
        if not self.tool_registry:
            return None
        
        # Check if the tool registry has a method to get tool description
        if hasattr(self.tool_registry, 'get_tool_description'):
            tool_desc = self.tool_registry.get_tool_description(tool_name)
            if tool_desc:
                # Convert tool description to ToolInfo
                parameters = []
                if hasattr(tool_desc, 'parameters'):
                    for param in tool_desc.parameters:
                        parameters.append(ToolParameterSchema(
                            name=param.name,
                            type=getattr(param.type, 'value', str(param.type)),
                            description=param.description,
                            required=getattr(param, 'required', True),
                            default=getattr(param, 'default', None),
                            enum=getattr(param, 'enum', None),
                            pattern=None
                        ))
                
                return ToolInfo(
                    tool_name=tool_desc.name,
                    display_name=tool_desc.name.replace("_", " ").title(),
                    description=tool_desc.description,
                    category=getattr(tool_desc, 'category', 'discord'),
                    adapter_id="discord",
                    adapter_type="discord",
                    adapter_instance_name="Discord Adapter",
                    parameters=parameters,
                    returns_schema={"type": "object", "description": getattr(tool_desc, 'returns', 'Tool result')},
                    examples=getattr(tool_desc, 'examples', None),
                    requires_auth=getattr(tool_desc, 'requires_auth', False),
                    rate_limit=getattr(tool_desc, 'rate_limit', None),
                    timeout_seconds=getattr(tool_desc, 'timeout_seconds', 30.0),
                    enabled=True,
                    health_status="healthy"
                )
        
        # Fallback to basic info if tool exists
        if tool_name in await self.get_available_tools():
            return ToolInfo(
                tool_name=tool_name,
                display_name=tool_name.replace("_", " ").title(),
                description=f"Discord tool: {tool_name}",
                category="discord",
                adapter_id="discord",
                adapter_type="discord",
                adapter_instance_name="Discord Adapter",
                parameters=[],
                returns_schema=None,
                examples=None,
                requires_auth=False,
                rate_limit=None,
                timeout_seconds=30.0,
                enabled=True,
                health_status="healthy"
            )
        
        return None
    
    async def get_all_tool_info(self) -> List[ToolInfo]:
        """Get detailed information about all available tools."""
        tools = []
        for tool_name in await self.get_available_tools():
            tool_info = await self.get_tool_info(tool_name)
            if tool_info:
                tools.append(tool_info)
        return tools
    
    async def validate_tool_parameters(self, tool_name: str, parameters: dict) -> bool:
        """Basic parameter validation using tool registry schemas.
        
        Args:
            tool_name: Name of the tool to validate parameters for
            parameters: Parameters to validate
            
        Returns:
            True if parameters are valid, False otherwise
        """
        if not self.tool_registry:
            return False
        
        try:
            schema = self.tool_registry.get_schema(tool_name)
            if not schema:
                return False
            
            return all(k in parameters for k in schema.keys())
            
        except Exception as e:
            logger.warning(f"Parameter validation failed for {tool_name}: {e}")
            return False
    
    def clear_tool_results(self) -> None:
        """Clear all cached tool results."""
        self._tool_results.clear()
    
    def get_cached_result_count(self) -> int:
        """Get the number of cached tool results.
        
        Returns:
            Number of cached results
        """
        return len(self._tool_results)
    
    def remove_cached_result(self, correlation_id: str) -> bool:
        """Remove a specific cached result.
        
        Args:
            correlation_id: The correlation ID to remove
            
        Returns:
            True if result was removed, False if not found
        """
        if correlation_id in self._tool_results:
            del self._tool_results[correlation_id]
            return True
        return False