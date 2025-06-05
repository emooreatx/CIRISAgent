"""
Multi-service sink implementation that routes actions to appropriate services
based on action type, with circuit breaker patterns and fallback support.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Union, Callable, List, Awaitable
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
from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage
from ..protocols.services import (
    CommunicationService,
    WiseAuthorityService,
    MemoryService,
    ToolService,
)
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus
from ..registries.circuit_breaker import CircuitBreakerError
from .base_sink import BaseMultiServiceSink

logger = logging.getLogger(__name__)


class MultiServiceActionSink(BaseMultiServiceSink):
    """
    Universal action sink that routes actions to appropriate services based on action type.
    Supports circuit breaker patterns, fallback mechanisms, and graceful degradation.
    """
    
    def __init__(self,
                 service_registry: Optional[Any] = None,
                 max_queue_size: int = 1000,
                 fallback_channel_id: Optional[str] = None) -> None:
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
            # Note: OBSERVE_MESSAGE removed - observation handled at adapter level
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
            # Note: OBSERVE_MESSAGE capabilities removed - observation handled at adapter level
        }

    async def _validate_action(self, action: ActionMessage) -> bool:
        """Validate action has required fields for its type"""
        if action.type == ActionType.SEND_MESSAGE:
            return bool(getattr(action, 'channel_id', None) and getattr(action, 'content', None))
        if action.type == ActionType.SEND_DEFERRAL:
            return bool(getattr(action, 'thought_id', None) and getattr(action, 'reason', None))
        return True

    async def _process_action(self, action: ActionMessage) -> None:
        if not await self._validate_action(action):
            logger.error(f"Invalid action payload: {asdict(action)}")
            return
        await super()._process_action(action)
    
    async def _execute_action_on_service(self, service: Any, action: ActionMessage) -> None:
        """Execute action on the appropriate service"""
        action_type = action.type
        
        try:
            if action_type == ActionType.SEND_MESSAGE:
                await self._handle_send_message(service, action)  # type: ignore
            elif action_type == ActionType.FETCH_MESSAGES:
                await self._handle_fetch_messages(service, action)  # type: ignore
            elif action_type == ActionType.FETCH_GUIDANCE:
                await self._handle_fetch_guidance(service, action)  # type: ignore
            elif action_type == ActionType.SEND_DEFERRAL:
                await self._handle_send_deferral(service, action)  # type: ignore
            elif action_type == ActionType.MEMORIZE:
                await self._handle_memorize(service, action)  # type: ignore
            elif action_type == ActionType.RECALL:
                await self._handle_recall(service, action)  # type: ignore
            elif action_type == ActionType.FORGET:
                await self._handle_forget(service, action)  # type: ignore
            elif action_type == ActionType.SEND_TOOL:
                await self._handle_send_tool(service, action)  # type: ignore
            elif action_type == ActionType.FETCH_TOOL:
                await self._handle_fetch_tool(service, action)  # type: ignore
            else:
                logger.error(f"No handler for action type: {action_type}")
                
        except Exception as e:
            logger.error(f"Error executing {action_type} on service {type(service).__name__}: {e}")
            raise
    
    async def _handle_send_message(self, service: CommunicationService, action: SendMessageAction) -> None:
        """Handle send message action"""
        success = await service.send_message(action.channel_id, action.content)
        if success:
            logger.info(f"Message sent via {type(service).__name__} to {action.channel_id}")
        else:
            logger.warning(f"Failed to send message via {type(service).__name__}")
    
    async def _handle_fetch_messages(self, service: CommunicationService, action: FetchMessagesAction) -> List[FetchedMessage]:
        """Handle fetch messages action"""
        messages = await service.fetch_messages(action.channel_id, action.limit)
        logger.info(f"Fetched {len(messages) if messages else 0} messages from {action.channel_id}")
        return messages
    
    async def _handle_fetch_guidance(self, service: WiseAuthorityService, action: FetchGuidanceAction) -> Optional[str]:
        """Handle fetch guidance action"""
        guidance = await service.fetch_guidance(action.context)
        logger.info(f"Received guidance from {type(service).__name__}")
        return guidance
    
    async def _handle_send_deferral(self, service: WiseAuthorityService, action: SendDeferralAction) -> None:
        """Handle submit deferral action"""
        success = await service.send_deferral(action.thought_id, action.reason)
        if success:
            logger.info(f"Deferral sent via {type(service).__name__} for thought {action.thought_id}")
        else:
            logger.warning(f"Failed to send deferral via {type(service).__name__}")
    
    async def _handle_memorize(self, service: MemoryService, action: MemorizeAction) -> Any:
        """Handle memorize action"""
        result = await service.memorize(action.node)
        if result.status == MemoryOpStatus.OK:
            logger.info(
                f"Stored memory {action.node.id} via {type(service).__name__}"
            )
        else:
            logger.warning(
                f"Failed to store memory {action.node.id} via {type(service).__name__}: {result.reason or result.error}"
            )
        return result
    
    async def _handle_recall(self, service: MemoryService, action: RecallAction) -> Any:
        """Handle recall action"""
        result = await service.recall(action.node)
        logger.info(
            f"Retrieved memory {action.node.id} via {type(service).__name__}"
        )
        return result
    
    async def _handle_forget(self, service: MemoryService, action: ForgetAction) -> Any:
        """Handle forget action"""
        result = await service.forget(action.node)
        if result.status == MemoryOpStatus.OK:
            logger.info(
                f"Deleted memory {action.node.id} via {type(service).__name__}"
            )
        else:
            logger.warning(
                f"Failed to delete memory {action.node.id} via {type(service).__name__}: {result.reason or result.error}"
            )
        return result
    
    async def _handle_send_tool(self, service: ToolService, action: SendToolAction) -> Any:
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
    
    async def _handle_fetch_tool(self, service: ToolService, action: FetchToolAction) -> Any:
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
    
    async def fetch_messages(self, handler_name: str, channel_id: str, limit: int = 10, metadata: Optional[Dict] = None) -> bool:
        """Convenience method to fetch messages"""
        action = FetchMessagesAction(
            handler_name=handler_name,
            metadata=metadata or {},
            channel_id=channel_id,
            limit=limit
        )
        return await self.enqueue_action(action)
    
    async def fetch_messages_sync(self, handler_name: str, channel_id: str, limit: int = 10, metadata: Optional[Dict] = None) -> Optional[List[FetchedMessage]]:
        """Convenience method to fetch messages synchronously and return the actual messages"""
        try:
            action = FetchMessagesAction(
                handler_name=handler_name,
                metadata=metadata or {},
                channel_id=channel_id,
                limit=limit
            )
            
            # Get service directly and call fetch_messages
            service = await self._get_service('communication', action)
            if service:
                messages = await self._handle_fetch_messages(service, action)  # type: ignore
                return messages
            else:
                logger.warning(f"No communication service available for fetch_messages_sync")
                return None
        except Exception as e:
            logger.error(f"Error in fetch_messages_sync: {e}")
            return None
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
                          correlation_id: Optional[str] = None, metadata: Optional[Dict] = None) -> ToolResult:
        """Convenience method to execute a tool"""
        action = SendToolAction(
            handler_name=handler_name,
            metadata=metadata or {},
            tool_name=tool_name,
            tool_args=tool_args,
            correlation_id=correlation_id
        )
        return await self.enqueue_action(action)

    # Memory convenience methods
    async def memorize(self, node: Any, handler_name: str = "memory", metadata: Optional[Dict] = None) -> Any:
        """Convenience method to memorize a node synchronously"""
        try:
            from ciris_engine.schemas.service_actions_v1 import MemorizeAction
            action = MemorizeAction(
                handler_name=handler_name,
                metadata=metadata or {},
                node=node
            )
            
            # Get service directly and call memorize
            service = await self._get_service('memory', action)
            if service:
                result = await self._handle_memorize(service, action)  # type: ignore
                return result
            else:
                logger.warning(f"No memory service available for memorize")
                return None
        except Exception as e:
            logger.error(f"Error in memorize: {e}")
            raise

    async def recall(self, node: Any, handler_name: str = "memory", metadata: Optional[Dict] = None) -> Any:
        """Convenience method to recall a node synchronously"""
        try:
            from ciris_engine.schemas.service_actions_v1 import RecallAction
            action = RecallAction(
                handler_name=handler_name,
                metadata=metadata or {},
                node=node
            )
            
            # Get service directly and call recall
            service = await self._get_service('memory', action)
            if service:
                result = await self._handle_recall(service, action)  # type: ignore
                return result
            else:
                logger.warning(f"No memory service available for recall")
                return None
        except Exception as e:
            logger.error(f"Error in recall: {e}")
            raise

    async def forget(self, node: Any, handler_name: str = "memory", metadata: Optional[Dict] = None) -> Any:
        """Convenience method to forget a node synchronously"""
        try:
            from ciris_engine.schemas.service_actions_v1 import ForgetAction
            action = ForgetAction(
                handler_name=handler_name,
                metadata=metadata or {},
                node=node
            )
            
            # Get service directly and call forget
            service = await self._get_service('memory', action)
            if service:
                result = await self._handle_forget(service, action)  # type: ignore
                return result
            else:
                logger.warning(f"No memory service available for forget")
                return None
        except Exception as e:
            logger.error(f"Error in forget: {e}")
            raise

    # Tool convenience methods
    async def execute_tool_sync(self, tool_name: str, tool_args: Dict[str, Any], 
                               correlation_id: Optional[str] = None, handler_name: str = "tool", 
                               metadata: Optional[Dict] = None) -> ToolResult:
        """Convenience method to execute a tool synchronously"""
        try:
            from ciris_engine.schemas.service_actions_v1 import SendToolAction
            action = SendToolAction(
                handler_name=handler_name,
                metadata=metadata or {},
                tool_name=tool_name,
                tool_args=tool_args,
                correlation_id=correlation_id
            )
            
            # Get service directly and call execute
            service = await self._get_service('tool', action)
            if service:
                result = await self._handle_send_tool(service, action)  # type: ignore
                return result
            else:
                logger.warning(f"No tool service available for execute_tool_sync")
                return None
        except Exception as e:
            logger.error(f"Error in execute_tool_sync: {e}")
            raise

    async def get_tool_result_sync(self, correlation_id: str, timeout: Optional[float] = None, 
                                  handler_name: str = "tool", metadata: Optional[Dict] = None) -> Optional[ToolResult]:
        """Convenience method to get tool result synchronously"""
        try:
            from ciris_engine.schemas.service_actions_v1 import FetchToolAction
            action = FetchToolAction(
                handler_name=handler_name,
                metadata=metadata or {},
                correlation_id=correlation_id,
                timeout=timeout
            )
            
            # Get service directly and call fetch
            service = await self._get_service('tool', action)
            if service:
                result = await self._handle_fetch_tool(service, action)  # type: ignore
                return result
            else:
                logger.warning(f"No tool service available for get_tool_result_sync")
                return None
        except Exception as e:
            logger.error(f"Error in get_tool_result_sync: {e}")
            raise

    # Existing convenience methods...

