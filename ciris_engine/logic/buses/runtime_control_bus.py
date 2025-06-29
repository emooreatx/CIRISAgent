"""
Runtime Control message bus - handles all runtime control operations with safety checks
"""

import logging
import asyncio
from typing import Optional, List, TYPE_CHECKING, Dict
from enum import Enum

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry

from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.protocols.services import RuntimeControlService
from ciris_engine.schemas.services.core.runtime import ProcessorQueueStatus, AdapterInfo
from ciris_engine.schemas.services.core.runtime import ProcessorControlResponse, ConfigSnapshot
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from .base_bus import BaseBus, BusMessage

logger = logging.getLogger(__name__)

class OperationPriority(str, Enum):
    """Priority levels for runtime operations"""
    CRITICAL = "critical"  # Shutdown, emergency stop
    HIGH = "high"         # Configuration changes
    NORMAL = "normal"     # Status queries
    LOW = "low"          # Metrics, non-essential ops

class RuntimeControlBus(BaseBus[RuntimeControlService]):
    """
    Message bus for all runtime control operations.

    CRITICAL: This bus manages system lifecycle and must:
    - Serialize configuration changes
    - Validate operations before execution
    - Maintain operation ordering
    - Provide graceful degradation
    """

    def __init__(self, service_registry: "ServiceRegistry", time_service: TimeServiceProtocol):
        super().__init__(
            service_type=ServiceType.RUNTIME_CONTROL,
            service_registry=service_registry
        )
        self._time_service = time_service
        # Track ongoing operations to prevent conflicts
        self._active_operations: Dict[str, asyncio.Task] = {}
        self._operation_lock = asyncio.Lock()
        self._shutting_down = False

    async def get_processor_queue_status(
        self,
        handler_name: str = "default"
    ) -> ProcessorQueueStatus:
        """Get processor queue status"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["get_processor_queue_status"]
        )

        if not service:
            logger.error(f"No runtime control service available for {handler_name}")
            # Return empty status on error
            return ProcessorQueueStatus(
                queue_size=0,
                processing=False,
                current_item=None,
                items_processed=0,
                average_processing_time=None
            )

        try:
            return await service.get_processor_queue_status()
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}", exc_info=True)
            # Return empty status on exception
            return ProcessorQueueStatus(
                queue_size=0,
                processing=False,
                current_item=None,
                items_processed=0,
                average_processing_time=None
            )

    async def shutdown_runtime(
        self,
        reason: str,
        handler_name: str = "default"
    ) -> ProcessorControlResponse:
        """Shutdown the runtime gracefully"""
        async with self._operation_lock:
            if self._shutting_down:
                logger.info("Shutdown already in progress")
                return ProcessorControlResponse(
                    success=True,
                    action="shutdown",
                    timestamp=self._time_service.now(),
                    result={"message": "Already shutting down"}
                )

            service = await self.get_service(
                handler_name=handler_name,
                required_capabilities=["shutdown_runtime"]
            )

            if not service:
                logger.error(f"No runtime control service available for {handler_name}")
                return ProcessorControlResponse(
                    success=False,
                    action="shutdown",
                    timestamp=self._time_service.now(),
                    error="Service unavailable"
                )

            try:
                logger.warning(f"RUNTIME SHUTDOWN triggered by {handler_name}: reason='{reason}'")
                self._shutting_down = True

                # Cancel all active operations
                for op_name, task in self._active_operations.items():
                    logger.info(f"Cancelling active operation: {op_name}")
                    task.cancel()

                self._active_operations.clear()

                response = await service.shutdown_runtime(reason)

                return response
            except Exception as e:
                logger.error(f"Exception during shutdown: {e}", exc_info=True)
                return ProcessorControlResponse(
                    success=False,
                    action="shutdown",
                    timestamp=self._time_service.now(),
                    error=str(e)
                )

    async def get_config(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False,
        handler_name: str = "default"
    ) -> ConfigSnapshot:
        """Get configuration value(s)"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["get_config"]
        )

        if not service:
            logger.error(f"No runtime control service available for {handler_name}")
            return ConfigSnapshot(
                configs={},
                version="unknown",
                metadata={"error": "Runtime control service unavailable"}
            )

        try:
            return await service.get_config(path, include_sensitive)
        except Exception as e:
            logger.error(f"Failed to get config: {e}", exc_info=True)
            return ConfigSnapshot(
                configs={},
                version="unknown",
                metadata={"error": str(e)}
            )

    async def get_runtime_status(
        self,
        handler_name: str = "default"
    ) -> dict:
        """Get runtime status - safe to call anytime"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["get_runtime_status"]
        )

        if not service:
            logger.error(f"No runtime control service available for {handler_name}")
            return {
                "status": "error",
                "message": "Runtime control service unavailable"
            }

        try:
            status = await service.get_runtime_status()

            # Add bus-level status
            status["bus_status"] = {
                "active_operations": list(self._active_operations.keys()),
                "shutting_down": self._shutting_down
            }

            return status
        except Exception as e:
            logger.error(f"Failed to get runtime status: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

    async def load_adapter(
        self,
        adapter_type: str,
        adapter_id: str,
        config: dict,
        auto_start: bool = True,
        handler_name: str = "default"
    ) -> AdapterInfo:
        """Load a new adapter instance"""
        if self._shutting_down:
            logger.warning("Cannot load adapter during shutdown")
            return AdapterInfo(
                adapter_id=adapter_id,
                adapter_type=adapter_type,
                status="error",
                loaded_at=self._time_service.now(),
                configuration={"error": "System shutting down"},
                metrics=None
            )

        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["load_adapter"]
        )

        if not service:
            logger.error(f"No runtime control service available for {handler_name}")
            return AdapterInfo(
                adapter_id=adapter_id,
                adapter_type=adapter_type,
                status="error",
                loaded_at=self._time_service.now(),
                configuration={"error": "Service unavailable"},
                metrics=None
            )

        try:
            logger.info(f"Loading adapter {adapter_id} of type {adapter_type}")
            response = await service.load_adapter(adapter_type, adapter_id, config, auto_start)
            return response
        except Exception as e:
            logger.error(f"Failed to load adapter: {e}", exc_info=True)
            return AdapterInfo(
                adapter_id=adapter_id,
                adapter_type=adapter_type,
                status="error",
                loaded_at=self._time_service.now(),
                configuration={"error": str(e)},
                metrics=None
            )

    async def unload_adapter(
        self,
        adapter_id: str,
        force: bool = False,
        handler_name: str = "default"
    ) -> AdapterInfo:
        """Unload an adapter instance"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["unload_adapter"]
        )

        if not service:
            logger.error(f"No runtime control service available for {handler_name}")
            return AdapterInfo(
                adapter_id=adapter_id,
                adapter_type="unknown",
                status="error",
                loaded_at=self._time_service.now(),
                configuration={"error": "Service unavailable"},
                metrics=None
            )

        try:
            logger.info(f"Unloading adapter {adapter_id}")
            response = await service.unload_adapter(adapter_id, force)
            return response
        except Exception as e:
            logger.error(f"Failed to unload adapter: {e}", exc_info=True)
            return AdapterInfo(
                adapter_id=adapter_id,
                adapter_type="unknown",
                status="error",
                loaded_at=self._time_service.now(),
                configuration={"error": str(e)},
                metrics=None
            )

    async def list_adapters(
        self,
        handler_name: str = "default"
    ) -> List[AdapterInfo]:
        """List all loaded adapters"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["list_adapters"]
        )

        if not service:
            logger.error(f"No runtime control service available for {handler_name}")
            return []

        try:
            return await service.list_adapters()
        except Exception as e:
            logger.error(f"Failed to list adapters: {e}", exc_info=True)
            return []

    async def pause_processing(
        self,
        handler_name: str = "default"
    ) -> bool:
        """Pause processor execution"""
        # Maps to pause_processing in the actual service
        if self._shutting_down:
            logger.warning("Cannot pause processor during shutdown")
            return False

        async with self._operation_lock:
            service = await self.get_service(
                handler_name=handler_name,
                required_capabilities=["pause_processing"]
            )

            if not service:
                logger.error(f"No runtime control service available for {handler_name}")
                return False

            try:
                logger.info(f"Pausing processor requested by {handler_name}")
                response = await service.pause_processing()
                result = response.success

                if result:
                    logger.info("Processor paused successfully")
                else:
                    logger.error("Failed to pause processor")

                return result
            except Exception as e:
                logger.error(f"Exception pausing processor: {e}", exc_info=True)
                return False

    async def resume_processing(
        self,
        handler_name: str = "default"
    ) -> bool:
        """Resume processor execution from paused state"""
        # Maps to resume_processing in the actual service
        if self._shutting_down:
            logger.warning("Cannot resume processor during shutdown")
            return False

        async with self._operation_lock:
            service = await self.get_service(
                handler_name=handler_name,
                required_capabilities=["resume_processing"]
            )

            if not service:
                logger.error(f"No runtime control service available for {handler_name}")
                return False

            try:
                logger.info(f"Resuming processor requested by {handler_name}")
                response = await service.resume_processing()
                result = response.success

                if result:
                    logger.info("Processor resumed successfully")
                else:
                    logger.error("Failed to resume processor")

                return result
            except Exception as e:
                logger.error(f"Exception resuming processor: {e}", exc_info=True)
                return False

    async def single_step(
        self,
        handler_name: str = "default"
    ) -> Optional[ProcessorControlResponse]:
        """Execute a single thought processing step"""
        # Maps to single_step returning ProcessorControlResponse
        if self._shutting_down:
            logger.warning("Cannot single-step during shutdown")
            return None

        async with self._operation_lock:
            service = await self.get_service(
                handler_name=handler_name,
                required_capabilities=["single_step"]
            )

            if not service:
                logger.error(f"No runtime control service available for {handler_name}")
                return None

            try:
                logger.debug(f"Single step requested by {handler_name}")
                response = await service.single_step()

                if response.success:
                    logger.info("Single step completed")
                    return response
                else:
                    logger.debug("Single step failed or no thoughts to process")
                    return None
            except Exception as e:
                logger.error(f"Exception during single step: {e}", exc_info=True)
                return None

    async def get_adapter_info(
        self,
        adapter_id: str,
        handler_name: str = "default"
    ) -> AdapterInfo:
        """Get detailed information about a specific adapter"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["get_adapter_info"]
        )

        if not service:
            logger.error(f"No runtime control service available for {handler_name}")
            return AdapterInfo(
                adapter_id=adapter_id,
                adapter_type="unknown",
                status="error",
                loaded_at=self._time_service.now(),
                configuration={"error": "Service unavailable"},
                metrics=None
            )

        try:
            return await service.get_adapter_info(adapter_id)
        except Exception as e:
            logger.error(f"Failed to get adapter info: {e}", exc_info=True)
            return AdapterInfo(
                adapter_id=adapter_id,
                adapter_type="unknown",
                status="error",
                loaded_at=self._time_service.now(),
                configuration={"error": str(e)},
                metrics=None
            )

    async def is_healthy(self, handler_name: str = "default") -> bool:
        """Check if runtime control service is healthy"""
        service = await self.get_service(handler_name=handler_name)
        if not service:
            return False
        try:
            return await service.is_healthy() and not self._shutting_down
        except Exception as e:
            logger.error(f"Failed to check health: {e}")
            return False

    async def get_capabilities(self, handler_name: str = "default") -> List[str]:
        """Get runtime control service capabilities"""
        service = await self.get_service(handler_name=handler_name)
        if not service:
            return []
        try:
            return await service.get_capabilities()
        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return []

    async def _process_message(self, message: BusMessage) -> None:
        """Process runtime control messages - most should be synchronous"""
        logger.warning(f"Runtime control operations should generally be synchronous: {type(message)}")
