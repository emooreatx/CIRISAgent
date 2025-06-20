"""
TelemetryService implementation that follows the protocol.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timezone

from ciris_engine.protocols.services import TelemetryService
from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
from ciris_engine.schemas.protocol_schemas_v1 import MetricDataPoint, ServiceStatus, ResourceLimits
from ciris_engine.telemetry.core import BasicTelemetryCollector

logger = logging.getLogger(__name__)


class ProtocolCompliantTelemetryService(TelemetryService):
    """TelemetryService implementation that wraps BasicTelemetryCollector and adds protocol methods."""
    
    def __init__(self) -> None:
        super().__init__()
        self._collector = BasicTelemetryCollector()
        self._resource_usage_cache: Dict[str, ResourceUsage] = {}
    
    async def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> bool:
        """Record a metric with optional tags."""
        try:
            # Use the collector's record_metric method
            await self._collector.record_metric(metric_name, value, tags or {})
            return True
        except Exception as e:
            logger.error(f"Failed to record metric {metric_name}: {e}")
            return False
    
    async def record_resource_usage(
        self, 
        service_name: str, 
        usage: ResourceUsage
    ) -> bool:
        """Record resource usage for a service."""
        try:
            # Cache the usage data
            self._resource_usage_cache[service_name] = usage
            
            # Record individual metrics
            await self.record_metric(f"{service_name}.tokens_used", float(usage.tokens_used or 0))
            await self.record_metric(f"{service_name}.tokens_input", float(usage.tokens_input or 0))
            await self.record_metric(f"{service_name}.tokens_output", float(usage.tokens_output or 0))
            
            if usage.cost_cents:
                await self.record_metric(f"{service_name}.cost_cents", usage.cost_cents)
                
            return True
        except Exception as e:
            logger.error(f"Failed to record resource usage for {service_name}: {e}")
            return False
    
    async def query_metrics(
        self,
        _metric_names: Optional[List[str]] = None,
        _service_names: Optional[List[str]] = None,
        _time_range: Optional[Tuple[datetime, datetime]] = None,
        _tags: Optional[Dict[str, str]] = None,
        _aggregation: Optional[str] = None
    ) -> List[MetricDataPoint]:
        """Query metrics with filtering and aggregation options."""
        try:
            # BasicTelemetryCollector doesn't have get_compact_telemetry yet
            # For now, return empty results
            results: List[MetricDataPoint] = []
            
            # TODO: Implement proper metric querying when BasicTelemetryCollector
            # is updated to implement the full TelemetryService protocol
            
            return results
        except Exception as e:
            logger.error(f"Failed to query metrics: {e}")
            return []
    
    async def get_service_status(
        self, 
        service_name: Optional[str] = None
    ) -> Union[ServiceStatus, Dict[str, ServiceStatus]]:
        """Get service status information."""
        try:
            if service_name:
                # Return specific service status
                usage = self._resource_usage_cache.get(service_name)
                return ServiceStatus(
                    service_name=service_name,
                    status="healthy" if usage else "unknown",
                    uptime_seconds=None,
                    last_heartbeat=datetime.now(timezone.utc),
                    metrics={
                        "has_usage": 1.0 if usage else 0.0
                    }
                )
            else:
                # Return all services status
                statuses: Dict[str, ServiceStatus] = {}
                for svc_name, usage in self._resource_usage_cache.items():
                    statuses[svc_name] = ServiceStatus(
                        service_name=svc_name,
                        status="healthy",
                        uptime_seconds=None,
                        last_heartbeat=datetime.now(timezone.utc),
                        metrics={
                            "tokens_used": float(usage.tokens_used) if usage.tokens_used else 0.0
                        }
                    )
                return statuses
        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            # Return a failed status
            return ServiceStatus(
                service_name=service_name or "telemetry",
                status="unhealthy",
                uptime_seconds=None,
                last_heartbeat=datetime.now(timezone.utc),
                metrics={"error": 1.0}
            )
    
    async def get_resource_limits(self) -> ResourceLimits:
        """Get resource usage limits."""
        return ResourceLimits(
            max_memory_mb=4096,
            max_cpu_percent=80.0,
            max_disk_gb=10.0,
            max_api_calls_per_minute=100,
            max_concurrent_operations=10
        )
    
    async def is_healthy(self) -> bool:
        """Health check for circuit breaker."""
        return True
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "record_metric",
            "record_resource_usage", 
            "query_metrics",
            "get_service_status",
            "get_resource_limits"
        ]