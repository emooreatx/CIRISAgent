"""
Multi-service sink implementation that routes actions to appropriate services
based on action type, with circuit breaker patterns and fallback support.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Union
from dataclasses import asdict
import json

from .action_types import (
    ActionType, ActionMessage, SendMessageAction, FetchMessagesAction,
    RequestGuidanceAction, SubmitDeferralAction, MemorizeAction, 
    RecallAction, ForgetAction, SendToolAction, FetchToolAction
)
from ..protocols.services import CommunicationService, WiseAuthorityService, MemoryService
from ..registries.circuit_breaker import CircuitBreakerError

logger = logging.getLogger(__name__)


class MultiServiceActionSink:
    """
    Universal action sink that routes actions to appropriate services based on action type.
    Supports circuit breaker patterns, fallback mechanisms, and graceful degradation.
    """
    
    def __init__(self, 
                 service_registry: Optional[Any] = None,
                 max_queue_size: int = 1000,
                 fallback_channel_id: Optional[str] = None):
        self.service_registry = service_registry
        self.fallback_channel_id = fallback_channel_id
        self._queue = asyncio.Queue(maxsize=max_queue_size)
        self._processing = False
        self._stop_event = asyncio.Event()
        
        # Action type to service type mapping
        self.service_routing = {
            ActionType.SEND_MESSAGE: 'communication',
            ActionType.FETCH_MESSAGES: 'communication',
            ActionType.REQUEST_GUIDANCE: 'wise_authority',
            ActionType.SUBMIT_DEFERRAL: 'wise_authority',
            ActionType.MEMORIZE: 'memory',
            ActionType.RECALL: 'memory',
            ActionType.FORGET: 'memory',
            ActionType.SEND_TOOL: 'tool',
            ActionType.FETCH_TOOL: 'tool',
        }
        
        # Pending tool results for correlation
        self._pending_tool_results: Dict[str, asyncio.Future] = {}
    
    async def enqueue_action(self, action: ActionMessage) -> bool:
        """Add action to processing queue with backpressure"""
        try:
            self._queue.put_nowait(action)
            return True
        except asyncio.QueueFull:
            logger.warning(f"MultiServiceActionSink queue full, rejecting action: {action.type}")
            return False
    
    async def start(self) -> None:
        """Start processing queued actions"""
        self._processing = True
        self._stop_event.clear()
        await self._start_processing()
    
    async def stop(self) -> None:
        """Stop processing actions"""
        self._processing = False
        self._stop_event.set()
    
    async def _start_processing(self):
        """Start processing queued actions with graceful shutdown"""
        logger.info("Starting MultiServiceActionSink processing")
        
        while self._processing:
            try:
                # Wait for either an action or stop event
                action_task = asyncio.create_task(self._queue.get())
                stop_task = asyncio.create_task(self._stop_event.wait())
                
                done, pending = await asyncio.wait(
                    [action_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=1.0
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                if stop_task in done:
                    logger.info("Stop event received for MultiServiceActionSink")
                    break
                
                if action_task in done:
                    action = action_task.result()
                    try:
                        await self._process_action(action)
                    except Exception as e:
                        logger.error(f"Error processing action {action.type}: {e}", exc_info=True)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in MultiServiceActionSink processing loop: {e}", exc_info=True)
        
        logger.info("Stopped MultiServiceActionSink processing")
    
    async def _process_action(self, action: ActionMessage):
        """Route action to appropriate service based on action type"""
        action_type = action.type
        service_type = self.service_routing.get(action_type)
        
        if not service_type:
            logger.error(f"No service routing defined for action type: {action_type}")
            return
        
        try:
            # Get service from registry
            service = await self._get_service(service_type, action)
            
            if service:
                await self._execute_action_on_service(service, action)
            else:
                await self._handle_fallback(action)
                
        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker open for {service_type}: {e}")
            await self._handle_fallback(action)
        except Exception as e:
            logger.error(f"Error processing action {action_type}: {e}", exc_info=True)
            await self._handle_fallback(action)
    
    async def _get_service(self, service_type: str, action: ActionMessage) -> Optional[Any]:
        """Get service from registry with action-specific requirements"""
        if not self.service_registry:
            return None
        
        # Determine required capabilities based on action type
        required_capabilities = self._get_required_capabilities(action.type)
        
        return await self.service_registry.get_service(
            handler=action.handler_name,
            service_type=service_type,
            required_capabilities=required_capabilities
        )
    
    def _get_required_capabilities(self, action_type: ActionType) -> list:
        """Get required capabilities for action type"""
        capability_map = {
            ActionType.SEND_MESSAGE: ['send_message'],
            ActionType.FETCH_MESSAGES: ['fetch_messages'],
            ActionType.REQUEST_GUIDANCE: ['request_guidance'],
            ActionType.SUBMIT_DEFERRAL: ['submit_deferral'],
            ActionType.MEMORIZE: ['store'],
            ActionType.RECALL: ['retrieve'],
            ActionType.FORGET: ['delete'],
            ActionType.SEND_TOOL: ['execute_tool'],
            ActionType.FETCH_TOOL: ['get_tool_result'],
        }
        return capability_map.get(action_type, [])
    
    async def _execute_action_on_service(self, service: Any, action: ActionMessage):
        """Execute action on the appropriate service"""
        action_type = action.type
        
        try:
            if action_type == ActionType.SEND_MESSAGE:
                await self._handle_send_message(service, action)
            elif action_type == ActionType.FETCH_MESSAGES:
                await self._handle_fetch_messages(service, action)
            elif action_type == ActionType.REQUEST_GUIDANCE:
                await self._handle_request_guidance(service, action)
            elif action_type == ActionType.SUBMIT_DEFERRAL:
                await self._handle_submit_deferral(service, action)
            elif action_type == ActionType.MEMORIZE:
                await self._handle_memorize(service, action)
            elif action_type == ActionType.RECALL:
                await self._handle_Recall(service, action)
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
    
    async def _handle_request_guidance(self, service: WiseAuthorityService, action: RequestGuidanceAction):
        """Handle request guidance action"""
        guidance = await service.request_guidance(action.context)
        logger.info(f"Received guidance from {type(service).__name__}")
        return guidance
    
    async def _handle_submit_deferral(self, service: WiseAuthorityService, action: SubmitDeferralAction):
        """Handle submit deferral action"""
        success = await service.submit_deferral(action.thought_id, action.reason)
        if success:
            logger.info(f"Deferral submitted via {type(service).__name__} for thought {action.thought_id}")
        else:
            logger.warning(f"Failed to submit deferral via {type(service).__name__}")
    
    async def _handle_memorize(self, service: MemoryService, action: MemorizeAction):
        """Handle memorize action"""
        success = await service.store(action.key, action.value, action.scope)
        if success:
            logger.info(f"Stored memory {action.key} via {type(service).__name__}")
        else:
            logger.warning(f"Failed to store memory via {type(service).__name__}")
    
    async def _handle_Recall(self, service: MemoryService, action: RecallAction):
        """Handle recall action"""
        value = await service.retrieve(action.key, action.scope)
        logger.info(f"Retrieved memory {action.key} via {type(service).__name__}")
        return value
    
    async def _handle_forget(self, service: MemoryService, action: ForgetAction):
        """Handle forget action"""
        success = await service.delete(action.key, action.scope)
        if success:
            logger.info(f"Deleted memory {action.key} via {type(service).__name__}")
        else:
            logger.warning(f"Failed to delete memory via {type(service).__name__}")
    
    async def _handle_send_tool(self, service: Any, action: SendToolAction):
        """Handle send tool action"""
        # For tool services, we'd need a ToolService protocol
        # For now, simulate tool execution
        correlation_id = action.correlation_id or f"tool_{asyncio.get_event_loop().time()}"
        
        # Store future for result correlation
        result_future = asyncio.get_event_loop().create_future()
        self._pending_tool_results[correlation_id] = result_future
        
        # Execute tool (would be actual service call)
        logger.info(f"Executing tool {action.tool_name} with correlation {correlation_id}")
        
        # Simulate async tool result
        asyncio.create_task(self._simulate_tool_result(correlation_id, action.tool_name))
    
    async def _handle_fetch_tool(self, service: Any, action: FetchToolAction):
        """Handle fetch tool result action"""
        correlation_id = action.correlation_id
        timeout = action.timeout
        
        future = self._pending_tool_results.get(correlation_id)
        if not future:
            logger.warning(f"No pending tool result for correlation {correlation_id}")
            return None
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"Retrieved tool result for correlation {correlation_id}")
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Tool result timeout for correlation {correlation_id}")
            return None
        finally:
            self._pending_tool_results.pop(correlation_id, None)
    
    async def _simulate_tool_result(self, correlation_id: str, tool_name: str):
        """Simulate async tool execution result"""
        await asyncio.sleep(0.1)  # Simulate execution time
        
        future = self._pending_tool_results.get(correlation_id)
        if future and not future.done():
            result = {
                "status": "success",
                "tool_name": tool_name,
                "correlation_id": correlation_id,
                "result": f"Simulated result for {tool_name}"
            }
            future.set_result(result)
    
    async def _handle_fallback(self, action: ActionMessage):
        """Handle action when no service is available"""
        action_type = action.type
        
        if action_type in [ActionType.SEND_MESSAGE, ActionType.SUBMIT_DEFERRAL]:
            # Fallback to logging for communication actions
            logger.warning(f"No service available for {action_type} - logging action: {asdict(action)}")
        elif action_type in [ActionType.MEMORIZE, ActionType.RECALL, ActionType.FORGET]:
            # Fallback to in-memory storage for memory actions
            logger.warning(f"No memory service available for {action_type} - using fallback")
        else:
            logger.warning(f"No fallback available for action type: {action_type}")
    
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
        action = SubmitDeferralAction(
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


class MultiServiceDeferralSink:
    """
    Universal deferral sink that routes deferrals to appropriate services based on service type.
    Supports circuit breaker patterns, fallback mechanisms, and graceful degradation.
    """
    
    def __init__(self, 
                 service_registry: Optional[Any] = None,
                 max_queue_size: int = 500,
                 fallback_channel_id: Optional[str] = None):
        self.service_registry = service_registry
        self.fallback_channel_id = fallback_channel_id
        self._queue = asyncio.Queue(maxsize=max_queue_size)
        self._processing = False
        self._stop_event = asyncio.Event()
    
    async def enqueue_deferral(self, deferral_data: Dict[str, Any]) -> bool:
        """Add deferral to processing queue with backpressure"""
        try:
            self._queue.put_nowait(deferral_data)
            return True
        except asyncio.QueueFull:
            logger.warning(f"MultiServiceDeferralSink queue full, rejecting deferral")
            return False
    
    async def start(self) -> None:
        """Start processing queued deferrals"""
        self._processing = True
        self._stop_event.clear()
        await self._start_processing()
    
    async def stop(self) -> None:
        """Stop processing deferrals"""
        self._processing = False
        self._stop_event.set()
    
    async def _start_processing(self):
        """Start processing queued deferrals with graceful shutdown"""
        logger.info("Starting MultiServiceDeferralSink processing")
        
        while self._processing:
            try:
                # Wait for either a deferral or stop event
                deferral_task = asyncio.create_task(self._queue.get())
                stop_task = asyncio.create_task(self._stop_event.wait())
                
                done, pending = await asyncio.wait(
                    [deferral_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=1.0
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                if stop_task in done:
                    logger.info("Stop event received for MultiServiceDeferralSink")
                    break
                
                if deferral_task in done:
                    deferral_data = deferral_task.result()
                    try:
                        await self._process_deferral(deferral_data)
                    except Exception as e:
                        logger.error(f"Error processing deferral: {e}", exc_info=True)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in MultiServiceDeferralSink processing loop: {e}", exc_info=True)
        
        logger.info("Stopped MultiServiceDeferralSink processing")
    
    async def _process_deferral(self, deferral_data: Dict[str, Any]):
        """Route deferral to appropriate service based on service type"""
        try:
            # Get communication service from registry for sending deferral
            comm_service = await self._get_service('communication')
            
            if comm_service:
                await self._send_deferral_via_service(comm_service, deferral_data)
            else:
                await self._handle_fallback(deferral_data)
                
        except CircuitBreakerError as e:
            logger.warning(f"Circuit breaker open for communication service: {e}")
            await self._handle_fallback(deferral_data)
        except Exception as e:
            logger.error(f"Error processing deferral: {e}", exc_info=True)
            await self._handle_fallback(deferral_data)
    
    async def _get_service(self, service_type: str) -> Optional[Any]:
        """Get service from registry"""
        if not self.service_registry:
            return None
        
        return await self.service_registry.get_service(
            handler="MultiServiceDeferralSink",
            service_type=service_type,
            required_capabilities=['send_message']
        )
    
    async def _send_deferral_via_service(self, comm_service: Any, deferral_data: Dict[str, Any]):
        """Send deferral using communication service"""
        task_id = deferral_data.get("task_id", "")
        thought_id = deferral_data.get("thought_id", "")
        reason = deferral_data.get("reason", "")
        package = deferral_data.get("package", {})
        channel_id = deferral_data.get("channel_id", self.fallback_channel_id)
        
        if not channel_id:
            logger.warning("No channel ID provided for deferral")
            return
        
        # Format deferral report
        if "metadata" in package and "user_nick" in package:
            report = (
                f"**Memory Deferral Report**\n"
                f"**Task ID:** `{task_id}`\n"
                f"**Deferred Thought ID:** `{thought_id}`\n"
                f"**User:** {package.get('user_nick')} Channel: {package.get('channel')}\n"
                f"**Reason:** {reason}\n"
                f"**Metadata:** ```json\n{json.dumps(package.get('metadata'), indent=2)}\n```"
            )
        else:
            report = (
                f"**Deferral Report**\n"
                f"**Task ID:** `{task_id}`\n"
                f"**Deferred Thought ID:** `{thought_id}`\n"
                f"**Reason:** {reason}\n"
                f"**Deferral Package:** ```json\n{json.dumps(package, indent=2)}\n```"
            )
        
        success = await comm_service.send_message(channel_id, report)
        if success:
            logger.info(f"Deferral sent via {type(comm_service).__name__} for thought {thought_id}")
        else:
            logger.warning(f"Failed to send deferral via {type(comm_service).__name__}")
    
    async def _handle_fallback(self, deferral_data: Dict[str, Any]):
        """Handle deferral when no service is available"""
        logger.warning(f"No service available for deferral - logging: {deferral_data}")
    
    # Convenience method for direct deferral submission
    async def send_deferral(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any], 
                           channel_id: Optional[str] = None) -> bool:
        """Convenience method to send a deferral"""
        deferral_data = {
            "task_id": task_id,
            "thought_id": thought_id,
            "reason": reason,
            "package": package,
            "channel_id": channel_id or self.fallback_channel_id
        }
        return await self.enqueue_deferral(deferral_data)
