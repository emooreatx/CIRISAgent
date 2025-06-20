"""
Telemetry message bus - handles all telemetry service operations
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from ciris_engine.schemas.protocol_schemas_v1 import MetricDataPoint

from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.protocols.services import TelemetryService
from .base_bus import BaseBus, BusMessage

logger = logging.getLogger(__name__)


class TelemetryBus(BaseBus[TelemetryService]):
    """
    Message bus for all telemetry operations.
    
    Handles:
    - record_metric
    - query_telemetry
    - record_log
    """
    
    def __init__(self, service_registry: Any):
        super().__init__(
            service_type=ServiceType.TELEMETRY,
            service_registry=service_registry
        )
    
    async def record_metric(
        self,
        metric_name: str,
        value: float,
        handler_name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> bool:
        """Record a metric value"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["record_metric"]
        )
        
        if not service:
            logger.debug(f"No telemetry service available for {handler_name}")
            return False
            
        try:
            result = await service.record_metric(metric_name, value, tags or {})
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to record metric {metric_name}: {e}", exc_info=True)
            return False
    
    async def query_telemetry(
        self,
        metric_names: List[str],
        handler_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        limit: int = 100
    ) -> List[MetricDataPoint]:
        """Query telemetry data"""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["query_telemetry"]
        )
        
        if not service:
            logger.debug(f"No telemetry service available for {handler_name}")
            return []
            
        try:
            # Convert string timestamps to datetime if provided
            time_range: Optional[Tuple[datetime, datetime]] = None
            if start_time and end_time:
                try:
                    start_dt = datetime.fromisoformat(start_time)
                    end_dt = datetime.fromisoformat(end_time)
                    time_range = (start_dt, end_dt)
                except ValueError:
                    logger.warning(f"Invalid timestamp format: start={start_time}, end={end_time}")
            
            result = await service.query_metrics(
                _metric_names=metric_names,
                _service_names=None,
                _time_range=time_range,
                _tags=tags,
                _aggregation=None
            )
            # Return the result directly - it's already a list
            return result if result else []
        except Exception as e:
            logger.error(f"Failed to query telemetry: {e}", exc_info=True)
            return []
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process a telemetry message - currently all telemetry operations are synchronous"""
        logger.warning(f"Telemetry operations should be synchronous, got queued message: {type(message)}")