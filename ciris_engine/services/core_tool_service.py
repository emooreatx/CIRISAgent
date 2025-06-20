"""
Core Tool Service: Provides system-wide tools that are always available to agents.
"""
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from ciris_engine.protocols.services import ToolService
from ciris_engine.adapters.tool_registry import ToolRegistry
from ciris_engine.adapters.core_tools import register_core_tools
from ciris_engine.schemas.protocol_schemas_v1 import ToolInfo, ToolParameterSchema, ToolExecutionResult
from ciris_engine.schemas.tool_schemas_v1 import ToolExecutionStatus

logger = logging.getLogger(__name__)


class CoreToolService(ToolService):
    """
    Service that provides core system tools like SELF_HELP.
    These tools are always available regardless of which adapters are loaded.
    """
    
    def __init__(self) -> None:
        super().__init__()
        self.tool_registry = ToolRegistry()
        self._pending_results: Dict[str, ToolExecutionResult] = {}
        
        # Register core system tools
        register_core_tools(self.tool_registry)
        logger.info("CoreToolService initialized with core system tools")
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolExecutionResult:
        """Execute a core system tool."""
        handler = self.tool_registry.get_handler(tool_name)
        if not handler:
            return ToolExecutionResult(
                success=False,
                error=f"Core tool '{tool_name}' not found",
                result={"available_tools": await self.get_available_tools()},
                execution_time=0,
                adapter_id="core",
                output=None,
                metadata=None
            )
        
        try:
            # Get correlation_id if provided
            correlation_id = parameters.pop("correlation_id", None)
            
            # Execute the tool
            import time
            start_time = time.time()
            result = await handler(parameters)
            execution_time = (time.time() - start_time) * 1000
            
            # Convert ToolResult to ToolExecutionResult
            execution_result = ToolExecutionResult(
                success=result.execution_status.value == "success",
                result=result.result_data,
                error=result.error_message,
                execution_time=execution_time / 1000,  # Convert to seconds
                adapter_id="core",
                output=None,
                metadata={"tool_name": result.tool_name, "correlation_id": correlation_id} if correlation_id else {"tool_name": result.tool_name}
            )
            
            # Store result if correlation_id provided
            if correlation_id:
                self._pending_results[correlation_id] = execution_result
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error executing core tool '{tool_name}': {e}")
            return ToolExecutionResult(
                success=False,
                error=str(e),
                result=None,
                execution_time=0,
                adapter_id="core",
                output=None,
                metadata=None
            )
    
    async def get_available_tools(self) -> List[str]:
        """Get list of available core tools."""
        return list(self.tool_registry._tools.keys())
    
    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """Get detailed information about a specific tool."""
        tool_desc = self.tool_registry.get_tool_description(tool_name)
        if not tool_desc:
            return None
        
        # Convert ToolDescription to ToolInfo
        parameters = [
            ToolParameterSchema(
                name=param.name,
                type=param.type.value,
                description=param.description,
                required=param.required,
                default=param.default,
                enum=param.enum,
                pattern=None  # Could add pattern validation later
            )
            for param in tool_desc.parameters
        ]
        
        return ToolInfo(
            tool_name=tool_desc.name,
            display_name=tool_desc.name.replace("_", " ").title(),
            description=tool_desc.description,
            category=tool_desc.category,
            adapter_id="core",
            adapter_type="core",
            adapter_instance_name="Core System Tools",
            parameters=parameters,
            returns_schema={"type": "object", "description": tool_desc.returns},
            examples=tool_desc.examples,
            requires_auth=tool_desc.requires_auth,
            rate_limit=tool_desc.rate_limit,
            timeout_seconds=tool_desc.timeout_seconds or 30.0,
            enabled=True,
            health_status="healthy"
        )
    
    async def get_all_tool_info(self) -> List[ToolInfo]:
        """Get detailed information about all available tools."""
        tools = []
        for tool_desc in self.tool_registry.list_tools():
            tool_info = await self.get_tool_info(tool_desc.name)
            if tool_info:
                tools.append(tool_info)
        return tools
    
    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[ToolExecutionResult]:
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
        return [
            "execute_tool", "get_available_tools", "validate_parameters", 
            "get_tool_result", "get_tool_info", "get_all_tool_info"
        ]
    
    async def start(self) -> None:
        """Start the service."""
        logger.info("CoreToolService started")
    
    async def stop(self) -> None:
        """Stop the service."""
        logger.info("CoreToolService stopped")