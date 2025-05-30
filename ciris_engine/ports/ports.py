"""
Abstract interfaces (ports) for CIRIS agent core.

Add new interfaces here to define boundaries between the core and external systems.
Examples: event sources, action sinks, deferral sinks, metrics sinks, etc.

To add a new port (interface), define an abstract base class (ABC) below.
For metrics (e.g., Prometheus), add a MetricsSink ABC with methods for reporting metrics.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

class EventSource(ABC):
    """Asynchronous source of events driving the agent."""
    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError
    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError
    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self._iterate()
    async def _iterate(self) -> AsyncIterator[Dict[str, Any]]:
        while False:
            yield {}

class ActionSink(ABC):
    """Consumer of agent actions with backpressure support and service registry integration."""
    
    def __init__(self, max_queue_size: int = 1000, service_registry: Optional[Any] = None):
        self._queue = asyncio.Queue(maxsize=max_queue_size)
        self._processing = False
        self._service_registry = service_registry
        self._stop_event = asyncio.Event()
    
    async def enqueue(self, action: Any) -> bool:
        """Add action to queue with backpressure"""
        try:
            self._queue.put_nowait(action)
            return True
        except asyncio.QueueFull:
            # Backpressure - reject the action
            logger.warning(f"ActionSink queue full, rejecting action: {type(action).__name__}")
            return False
    
    async def start(self) -> None:
        """Start processing queued actions"""
        self._processing = True
        self._stop_event.clear()
        await self.start_processing()
    
    async def stop(self) -> None:
        """Stop processing actions"""
        self._processing = False
        self._stop_event.set()
    
    async def start_processing(self):
        """Start processing queued actions with graceful shutdown"""
        logger.info(f"Starting {self.__class__.__name__} processing")
        
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
                    logger.info(f"Stop event received for {self.__class__.__name__}")
                    break
                
                if action_task in done:
                    action = action_task.result()
                    try:
                        await self._process_action(action)
                    except Exception as e:
                        logger.error(f"Error processing action in {self.__class__.__name__}: {e}", exc_info=True)
                        # Continue processing other actions
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in {self.__class__.__name__} processing loop: {e}", exc_info=True)
        
        logger.info(f"Stopped {self.__class__.__name__} processing")
    
    async def get_service(self, service_type: str, **kwargs) -> Optional[Any]:
        """Get a service from the registry if available"""
        if self._service_registry:
            return await self._service_registry.get_service(
                handler=self.__class__.__name__,
                service_type=service_type,
                **kwargs
            )
        return None
    
    @abstractmethod
    async def _process_action(self, action: Any):
        """Process a single action - implemented by concrete sinks"""
        pass
    
    # Backward compatibility methods
    @abstractmethod
    async def send_message(self, channel_id: str, content: str) -> None:
        raise NotImplementedError
    
    @abstractmethod
    async def run_tool(self, name: str, args: Dict[str, Any]) -> Any:
        raise NotImplementedError

class DeferralSink(ABC):
    """Specialized sink for sending deferral packages and handling WA corrections with backpressure support."""
    
    def __init__(self, max_queue_size: int = 500, service_registry: Optional[Any] = None):
        self._queue = asyncio.Queue(maxsize=max_queue_size)
        self._processing = False
        self._service_registry = service_registry
        self._stop_event = asyncio.Event()
    
    async def enqueue_deferral(self, deferral_data: Dict[str, Any]) -> bool:
        """Add deferral to queue with backpressure"""
        try:
            self._queue.put_nowait(deferral_data)
            return True
        except asyncio.QueueFull:
            logger.warning("DeferralSink queue full, rejecting deferral")
            return False
    
    async def start(self) -> None:
        """Start processing queued deferrals"""
        self._processing = True
        self._stop_event.clear()
        await self.start_processing()
    
    async def stop(self) -> None:
        """Stop processing deferrals"""
        self._processing = False
        self._stop_event.set()
    
    async def start_processing(self):
        """Start processing queued deferrals with graceful shutdown"""
        logger.info(f"Starting {self.__class__.__name__} processing")
        
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
                    logger.info(f"Stop event received for {self.__class__.__name__}")
                    break
                
                if deferral_task in done:
                    deferral_data = deferral_task.result()
                    try:
                        await self._process_deferral(deferral_data)
                    except Exception as e:
                        logger.error(f"Error processing deferral in {self.__class__.__name__}: {e}", exc_info=True)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in {self.__class__.__name__} processing loop: {e}", exc_info=True)
        
        logger.info(f"Stopped {self.__class__.__name__} processing")
    
    async def get_service(self, service_type: str, **kwargs) -> Optional[Any]:
        """Get a service from the registry if available"""
        if self._service_registry:
            return await self._service_registry.get_service(
                handler=self.__class__.__name__,
                service_type=service_type,
                **kwargs
            )
        return None
    
    async def _process_deferral(self, deferral_data: Dict[str, Any]):
        """Process a single deferral - calls the abstract send_deferral method"""
        await self.send_deferral(
            task_id=deferral_data.get("task_id", ""),
            thought_id=deferral_data.get("thought_id", ""),
            reason=deferral_data.get("reason", ""),
            package=deferral_data.get("package", {})
        )
    
    # Abstract methods for backward compatibility
    @abstractmethod
    async def send_deferral(
        self,
        task_id: str,
        thought_id: str,
        reason: str,
        package: Dict[str, Any],
    ) -> None:
        """Send a deferral report to the WA channel."""
        raise NotImplementedError
    
    async def process_possible_correction(self, msg: Any, raw_message: Any) -> bool:
        """Handle WA correction replies if applicable. Return True if handled."""
        return False

class FeedbackSink(ABC):
    """Sink for processing incoming feedback/corrections (e.g., WA, user feedback)."""
    @abstractmethod
    async def process_feedback(self, msg: Any, raw_message: Any) -> bool:
        """Process incoming feedback/correction and create follow-up thoughts as needed."""
        raise NotImplementedError

# Example: To add Prometheus-style metrics, define a MetricsSink ABC here.
# class MetricsSink(ABC):
#     @abstractmethod
#     def observe(self, metric_name: str, value: float, labels: Dict[str, str] = None) -> None:
#         ...
