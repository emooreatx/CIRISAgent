"""Discord tool handling component for tool execution operations."""
import discord
import logging
import asyncio
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ciris_engine.schemas.correlation_schemas_v1 import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine import persistence

logger = logging.getLogger(__name__)


class DiscordToolHandler:
    """Handles Discord tool execution and result management."""
    
    def __init__(self, tool_registry: Optional[Any] = None, client: Optional[discord.Client] = None) -> None:
        """Initialize the tool handler.
        
        Args:
            tool_registry: Registry of available tools
            client: Discord client instance
        """
        self.tool_registry = tool_registry
        self.client = client
        self._tool_results: Dict[str, Dict[str, Any]] = {}
    
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
    
    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
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
            raise RuntimeError("Tool registry not configured")
        
        handler = self.tool_registry.get_handler(tool_name)
        if not handler:
            raise RuntimeError(f"Tool handler for '{tool_name}' not found")
        
        correlation_id = tool_args.get("correlation_id", str(uuid.uuid4()))
        
        # Record the tool execution start
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=correlation_id,
                service_type="discord",
                handler_name="DiscordAdapter",
                action_type=tool_name,
                request_data=tool_args,
                status=ServiceCorrelationStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        
        try:
            # Execute the tool with the Discord client
            tool_args_with_bot = {**tool_args, "bot": self.client}
            result = await handler(tool_args_with_bot)
            
            # Convert result to dictionary if needed
            result_dict = result if isinstance(result, dict) else result.__dict__
            
            # Store the result for later retrieval
            if correlation_id:
                self._tool_results[correlation_id] = result_dict
                persistence.update_correlation(
                    correlation_id,
                    response_data=result_dict,
                    status=ServiceCorrelationStatus.COMPLETED,
                )
            
            return result_dict
            
        except Exception as e:
            logger.exception(f"Tool execution failed for {tool_name}: {e}")
            error_result = {"error": str(e), "tool_name": tool_name}
            
            if correlation_id:
                persistence.update_correlation(
                    correlation_id,
                    response_data=error_result,
                    status=ServiceCorrelationStatus.FAILED,
                )
            
            raise
    
    async def get_tool_result(self, correlation_id: str, timeout: int = 10) -> Dict[str, Any]:
        """Fetch a tool result by correlation ID from the internal cache.
        
        Args:
            correlation_id: The correlation ID of the tool execution
            timeout: Maximum time to wait for the result in seconds
            
        Returns:
            Tool result dictionary or not_found status
        """
        # Poll for the result with timeout
        for _ in range(timeout * 10):  # Check every 0.1 seconds
            if correlation_id in self._tool_results:
                return self._tool_results.pop(correlation_id)
            await asyncio.sleep(0.1)
        
        logger.warning(f"Tool result for correlation_id {correlation_id} not found after {timeout}s")
        return {"correlation_id": correlation_id, "status": "not_found"}
    
    async def get_available_tools(self) -> List[str]:
        """Return names of registered Discord tools.
        
        Returns:
            List of available tool names
        """
        if not self.tool_registry:
            return []
        
        # Handle different tool registry interfaces
        if hasattr(self.tool_registry, 'tools'):
            return list(self.tool_registry.tools.keys())
        elif hasattr(self.tool_registry, 'get_tools'):
            return list(self.tool_registry.get_tools().keys())
        else:
            logger.warning("Tool registry interface not recognized")
            return []
    
    async def validate_tool_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
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
            
            # Basic validation: check if all required keys are present
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