"""
Multi-service sink implementation that routes actions to appropriate services
based on action type, with circuit breaker patterns and fallback support.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Union, Callable, List
from dataclasses import asdict
import json
from abc import ABC, abstractmethod

from ciris_engine.schemas.service_actions_v1 import (
    ActionType,
    ActionMessage,
    SendMessageAction,
    FetchMessagesAction,
    FetchGuidanceAction,
    SendDeferralAction,
    MemorizeAction,
    RecallAction,
    ForgetAction,
    SendToolAction,
    FetchToolAction,
)
from ..protocols.services import CommunicationService, WiseAuthorityService, MemoryService, ToolService
from ..registries.circuit_breaker import CircuitBreakerError
from .base_sink import BaseMultiServiceSink
from .message_sink import MultiServiceMessageSink
from .memory_sink import MultiServiceMemorySink
from .tool_sink import MultiServiceToolSink
from .deferral_sink import MultiServiceDeferralSink

logger = logging.getLogger(__name__)


class MultiServiceActionSink(BaseMultiServiceSink):
    """
    Universal action sink that routes actions to appropriate services based on action type.
    Supports circuit breaker patterns, fallback mechanisms, and graceful degradation.
    """
    
    def __init__(self, 
                 service_registry: Optional[Any] = None,
                 max_queue_size: int = 1000,
                 fallback_channel_id: Optional[str] = None):
        super().__init__(service_registry, max_queue_size, fallback_channel_id)
        # Pending tool results for correlation
        self._pending_tool_results: Dict[str, asyncio.Future] = {}
    
    @property
    def service_routing(self) -> Dict[ActionType, str]:
        """Map action types to service types"""
        return {
            ActionType.SEND_MESSAGE: 'communication',
            ActionType.FETCH_MESSAGES: 'communication',
            ActionType.FETCH_GUIDANCE: 'wise_authority',
            ActionType.SEND_DEFERRAL: 'wise_authority',
            ActionType.MEMORIZE: 'memory',
            ActionType.RECALL: 'memory',
            ActionType.FORGET: 'memory',
            ActionType.SEND_TOOL: 'tool',
            ActionType.FETCH_TOOL: 'tool',
        }
    
    @property
    def capability_map(self) -> Dict[ActionType, List[str]]:
        """Map action types to required capabilities"""
        return {
            ActionType.SEND_MESSAGE: ['send_message'],
            ActionType.FETCH_MESSAGES: ['fetch_messages'],
            ActionType.FETCH_GUIDANCE: ['fetch_guidance'],
            ActionType.SEND_DEFERRAL: ['send_deferral'],
            ActionType.MEMORIZE: ['memorize'],
            ActionType.RECALL: ['recall'],
            ActionType.FORGET: ['forget'],
            ActionType.SEND_TOOL: ['execute_tool'],
            ActionType.FETCH_TOOL: ['get_tool_result'],
        }
    
    async def _execute_action_on_service(self, service: Any, action: ActionMessage):
        """Execute action on the appropriate service"""
        action_type = action.type
        
        try:
            if action_type == ActionType.SEND_MESSAGE:
                await self._handle_send_message(service, action)
            elif action_type == ActionType.FETCH_MESSAGES:
                await self._handle_fetch_messages(service, action)
            elif action_type == ActionType.FETCH_GUIDANCE:
                await self._handle_fetch_guidance(service, action)
            elif action_type == ActionType.SEND_DEFERRAL:
                await self._handle_send_deferral(service, action)
            elif action_type == ActionType.MEMORIZE:
                await self._handle_memorize(service, action)
            elif action_type == ActionType.RECALL:
                await self._handle_recall(service, action)
            elif action_type == ActionType.FORGET:
                await self._handle_forget(service, action)
            elif action_type == ActionType.SEND_TOOL:
                await self._handle_send_tool(service, action)
            elif action_type == ActionType.FETCH_TOOL:
                await self._handle_fetch_tool(service, action)
            else:
                logger.error(f"No handler for action type: {action_type}")
                
        except Exception as e:
            logger.error(f"Error executing {action_type} on service {type(service).__name__}: {e}")
            raise
    
    async def _handle_send_message(self, service: CommunicationService, action: SendMessageAction):
        """Handle send message action"""
        success = await service.send_message(action.channel_id, action.content)
        if success:
            logger.info(f"Message sent via {type(service).__name__} to {action.channel_id}")
        else:
            logger.warning(f"Failed to send message via {type(service).__name__}")
    
    async def _handle_fetch_messages(self, service: CommunicationService, action: FetchMessagesAction):
        """Handle fetch messages action"""
        messages = await service.fetch_messages(action.channel_id, action.limit)
        logger.info(f"Fetched {len(messages) if messages else 0} messages from {action.channel_id}")
        return messages
    
    async def _handle_fetch_guidance(self, service: WiseAuthorityService, action: FetchGuidanceAction):
        """Handle fetch guidance action"""
        guidance = await service.fetch_guidance(action.context)
        logger.info(f"Received guidance from {type(service).__name__}")
        return guidance
    
    async def _handle_send_deferral(self, service: WiseAuthorityService, action: SendDeferralAction):
        """Handle submit deferral action"""
        success = await service.send_deferral(action.thought_id, action.reason)
        if success:
            logger.info(f"Deferral sent via {type(service).__name__} for thought {action.thought_id}")
        else:
            logger.warning(f"Failed to send deferral via {type(service).__name__}")
    
    async def _handle_memorize(self, service: MemoryService, action: MemorizeAction):
        """Handle memorize action"""
        success = await service.memorize(action.key, action.value, action.scope)
        if success:
            logger.info(f"Stored memory {action.key} via {type(service).__name__}")
        else:
            logger.warning(f"Failed to store memory via {type(service).__name__}")
    
    async def _handle_recall(self, service: MemoryService, action: RecallAction):
        """Handle recall action"""
        value = await service.recall(action.key, action.scope)
        logger.info(f"Retrieved memory {action.key} via {type(service).__name__}")
        return value
    
    async def _handle_forget(self, service: MemoryService, action: ForgetAction):
        """Handle forget action"""
        success = await service.forget(action.key, action.scope)
        if success:
            logger.info(f"Deleted memory {action.key} via {type(service).__name__}")
        else:
            logger.warning(f"Failed to delete memory via {type(service).__name__}")
    
    async def _handle_send_tool(self, service: ToolService, action: SendToolAction):
        """Handle send tool action"""
        # Execute tool using the ToolService
        try:
            result = await service.execute_tool(action.tool_name, action.tool_args)
            correlation_id = action.correlation_id or f"tool_{asyncio.get_event_loop().time()}"
            
            logger.info(f"Executed tool {action.tool_name} with correlation {correlation_id}")
            
            # Store result for potential retrieval
            if correlation_id and hasattr(self, '_tool_results'):
                self._tool_results[correlation_id] = result
            
            return result
        except Exception as e:
            logger.error(f"Error executing tool {action.tool_name}: {e}")
            raise
    
    async def _handle_fetch_tool(self, service: ToolService, action: FetchToolAction):
        """Handle fetch tool result action"""
        try:
            result = await service.get_tool_result(action.correlation_id, action.timeout)
            if result:
                logger.info(f"Retrieved tool result for correlation {action.correlation_id}")
            else:
                logger.warning(f"No tool result found for correlation {action.correlation_id}")
            return result
        except Exception as e:
            logger.error(f"Error fetching tool result for {action.correlation_id}: {e}")
            raise
    
    # Convenience methods for common actions
    async def send_message(self, handler_name: str, channel_id: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Convenience method to send a message"""
        action = SendMessageAction(
            handler_name=handler_name,
            metadata=metadata or {},
            channel_id=channel_id,
            content=content
        )
        return await self.enqueue_action(action)
    
    async def submit_deferral(self, handler_name: str, thought_id: str, reason: str, metadata: Optional[Dict] = None) -> bool:
        """Convenience method to submit a deferral"""
        action = SendDeferralAction(
            handler_name=handler_name,
            metadata=metadata or {},
            thought_id=thought_id,
            reason=reason
        )
        return await self.enqueue_action(action)
    
    async def execute_tool(self, handler_name: str, tool_name: str, tool_args: Dict[str, Any], 
                          correlation_id: Optional[str] = None, metadata: Optional[Dict] = None) -> bool:
        """Convenience method to execute a tool"""
        action = SendToolAction(
            handler_name=handler_name,
            metadata=metadata or {},
            tool_name=tool_name,
            tool_args=tool_args,
            correlation_id=correlation_id
        )
        return await self.enqueue_action(action)
