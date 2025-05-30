"""
Base sink class for multi-service sinks.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, List
from dataclasses import asdict
from abc import ABC, abstractmethod
from ciris_engine.schemas.service_actions_v1 import ActionType, ActionMessage
from ..registries.circuit_breaker import CircuitBreakerError

logger = logging.getLogger(__name__)

class BaseMultiServiceSink(ABC):
    """
    Base class for multi-service sinks providing common functionality for
    routing actions to appropriate services with circuit breaker patterns.
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

    @property
    @abstractmethod
    def service_routing(self) -> Dict[ActionType, str]:
        pass

    @property
    @abstractmethod
    def capability_map(self) -> Dict[ActionType, List[str]]:
        pass

    @abstractmethod
    async def _execute_action_on_service(self, service: Any, action: ActionMessage):
        pass

    async def enqueue_action(self, action: ActionMessage) -> bool:
        try:
            self._queue.put_nowait(action)
            return True
        except asyncio.QueueFull:
            logger.warning(f"{self.__class__.__name__} queue full, rejecting action: {action.type}")
            return False

    async def start(self) -> None:
        self._processing = True
        self._stop_event.clear()
        await self._start_processing()

    async def stop(self) -> None:
        self._processing = False
        self._stop_event.set()

    async def _start_processing(self):
        logger.info(f"Starting {self.__class__.__name__} processing")
        while self._processing:
            try:
                action_task = asyncio.create_task(self._queue.get())
                stop_task = asyncio.create_task(self._stop_event.wait())
                done, pending = await asyncio.wait(
                    [action_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=1.0
                )
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                if stop_task in done:
                    logger.info(f"Stop event received for {self.__class__.__name__}")
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
                logger.error(f"Unexpected error in {self.__class__.__name__} processing loop: {e}", exc_info=True)
        logger.info(f"Stopped {self.__class__.__name__} processing")

    async def _process_action(self, action: ActionMessage):
        action_type = action.type
        service_type = self.service_routing.get(action_type)
        if not service_type:
            logger.error(f"No service routing defined for action type: {action_type}")
            return
        try:
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
        if not self.service_registry:
            return None
        required_capabilities = self.capability_map.get(action.type, [])
        return await self.service_registry.get_service(
            handler=action.handler_name,
            service_type=service_type,
            required_capabilities=required_capabilities
        )

    async def _handle_fallback(self, action: ActionMessage):
        logger.warning(f"No service available for {action.type} - logging action: {asdict(action)}")
