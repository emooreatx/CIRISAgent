"""
Service-aware sink implementations that integrate with the service registry.
These demonstrate how to use the registry system with fallback support.
"""

import logging
from typing import Any, Dict, Optional
from .ports import ActionSink, DeferralSink
from ..protocols.services import CommunicationService, WiseAuthorityService

logger = logging.getLogger(__name__)


class ServiceAwareActionSink(ActionSink):
    """
    Action sink that uses the service registry to find communication services
    with automatic fallback support.
    """
    
    def __init__(self, 
                 max_queue_size: int = 1000, 
                 service_registry: Optional[Any] = None,
                 fallback_channel_id: Optional[str] = None):
        super().__init__(max_queue_size, service_registry)
        self.fallback_channel_id = fallback_channel_id
    
    async def _process_action(self, action: Any):
        """Process actions using service registry with fallback"""
        action_type = getattr(action, 'action_type', 'unknown')
        
        if action_type == 'send_message':
            await self._handle_send_message(action)
        elif action_type == 'run_tool':
            await self._handle_run_tool(action)
        else:
            logger.warning(f"Unknown action type: {action_type}")
    
    async def _handle_send_message(self, action: Any):
        """Handle send message actions with service fallback"""
        channel_id = getattr(action, 'channel_id', self.fallback_channel_id)
        content = getattr(action, 'content', '')
        
        # Try to get communication service from registry
        comm_service = await self.get_service('communication', 
                                              required_capabilities=['send_message'])
        
        if comm_service and isinstance(comm_service, CommunicationService):
            try:
                success = await comm_service.send_message(channel_id, content)
                if success:
                    logger.info(f"Message sent via registry service: {type(comm_service).__name__}")
                    return
                else:
                    logger.warning(f"Registry service failed to send message: {type(comm_service).__name__}")
            except Exception as e:
                logger.error(f"Error using registry service {type(comm_service).__name__}: {e}")
        
        # Fallback to legacy send_message method
        logger.info("Falling back to legacy send_message method")
        await self.send_message(channel_id, content)
    
    async def _handle_run_tool(self, action: Any):
        """Handle tool execution actions"""
        tool_name = getattr(action, 'tool_name', '')
        tool_args = getattr(action, 'args', {})
        
        # For now, fallback to legacy method
        # Could be extended to use a ToolService from registry
        result = await self.run_tool(tool_name, tool_args)
        logger.info(f"Tool {tool_name} executed with result: {result}")
    
    async def send_message(self, channel_id: str, content: str) -> None:
        """Legacy method - should be overridden by concrete implementations"""
        logger.error("Legacy send_message not implemented in concrete sink")
        raise NotImplementedError
    
    async def run_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Legacy method - should be overridden by concrete implementations"""
        logger.error("Legacy run_tool not implemented in concrete sink")
        raise NotImplementedError


class ServiceAwareDeferralSink(DeferralSink):
    """
    Deferral sink that uses the service registry to find WA services
    with automatic fallback support.
    """
    
    def __init__(self, 
                 max_queue_size: int = 500, 
                 service_registry: Optional[Any] = None,
                 fallback_channel_id: Optional[str] = None):
        super().__init__(max_queue_size, service_registry)
        self.fallback_channel_id = fallback_channel_id
    
    async def send_deferral(self,
                           task_id: str,
                           thought_id: str,
                           reason: str,
                           package: Dict[str, Any]) -> None:
        """Send deferral using service registry with fallback"""
        
        # Try to get WA service from registry
        wa_service = await self.get_service('wise_authority')
        
        if wa_service and isinstance(wa_service, WiseAuthorityService):
            try:
                success = await wa_service.submit_deferral(thought_id, reason)
                if success:
                    logger.info(f"Deferral sent via registry WA service: {type(wa_service).__name__}")
                    return
                else:
                    logger.warning(f"Registry WA service failed to submit deferral: {type(wa_service).__name__}")
            except Exception as e:
                logger.error(f"Error using registry WA service {type(wa_service).__name__}: {e}")
        
        # Try communication service as fallback
        comm_service = await self.get_service('communication',
                                              required_capabilities=['send_message'])
        
        if comm_service and isinstance(comm_service, CommunicationService):
            try:
                deferral_message = f"**DEFERRAL**\\nTask: {task_id}\\nThought: {thought_id}\\nReason: {reason}"
                success = await comm_service.send_message(self.fallback_channel_id or "default", deferral_message)
                if success:
                    logger.info(f"Deferral sent via communication service: {type(comm_service).__name__}")
                    return
            except Exception as e:
                logger.error(f"Error using communication service for deferral: {e}")
        
        # If all else fails, log the deferral
        logger.warning(f"No service available for deferral - logging: Task={task_id}, Thought={thought_id}, Reason={reason}")


class ExampleDiscordActionSink(ServiceAwareActionSink):
    """
    Example implementation showing how to extend ServiceAwareActionSink
    for a specific communication platform (Discord).
    """
    
    def __init__(self, discord_client, default_channel_id: str, **kwargs):
        super().__init__(**kwargs)
        self.discord_client = discord_client
        self.default_channel_id = default_channel_id
    
    async def send_message(self, channel_id: str, content: str) -> None:
        """Legacy fallback implementation for Discord"""
        try:
            channel = self.discord_client.get_channel(int(channel_id or self.default_channel_id))
            if channel:
                await channel.send(content)
                logger.info(f"Message sent via legacy Discord method to channel {channel_id}")
            else:
                logger.error(f"Discord channel not found: {channel_id}")
        except Exception as e:
            logger.error(f"Error sending Discord message via legacy method: {e}")
    
    async def run_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Legacy fallback implementation for tool execution"""
        logger.info(f"Legacy tool execution: {name} with args {args}")
        # Simple mock implementation
        return {"status": "completed", "tool": name, "args": args}
