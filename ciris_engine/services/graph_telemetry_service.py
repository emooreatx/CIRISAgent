"""
Graph-based TelemetryService that stores all metrics as memories in the graph.

This implements the "Graph Memory as Identity Architecture" patent by routing
all telemetry data through the memory system as TSDBGraphNodes.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timezone

from ciris_engine.protocols.services import TelemetryService, MemoryService
from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
from ciris_engine.schemas.protocol_schemas_v1 import MetricDataPoint, ServiceStatus, ResourceLimits
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus
from ciris_engine.message_buses.memory_bus import MemoryBus

logger = logging.getLogger(__name__)


class GraphTelemetryService(TelemetryService):
    """
    TelemetryService that stores all metrics as graph memories.
    
    This service implements the vision where "everything is a memory" by
    converting telemetry data into TSDBGraphNodes stored in the memory graph.
    """
    
    def __init__(self, memory_bus: Optional[MemoryBus] = None) -> None:
        super().__init__()
        self._memory_bus = memory_bus
        self._service_registry: Optional[Any] = None
        self._resource_limits = ResourceLimits(
            max_memory_mb=4096,
            max_cpu_percent=80.0,
            max_disk_gb=100.0,
            max_api_calls_per_minute=1000,
            max_concurrent_operations=50
        )
        # Cache for recent metrics (for quick status queries)
        self._recent_metrics: Dict[str, List[MetricDataPoint]] = {}
        self._max_cached_metrics = 100
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry for accessing memory bus."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            # Try to get memory bus from registry
            try:
                from ciris_engine.message_buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
    
    async def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Record a metric by storing it as a memory in the graph.
        
        This creates a TSDBGraphNode and stores it via the MemoryService,
        implementing the unified telemetry flow.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for telemetry storage")
                return False
            
            # Add standard telemetry tags
            metric_tags = tags or {}
            metric_tags.update({
                "source": "telemetry",
                "metric_type": "operational",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Store as memory via the bus
            result = await self._memory_bus.memorize_metric(
                metric_name=metric_name,
                value=value,
                tags=metric_tags,
                scope="local",  # Operational metrics use local scope
                handler_name="telemetry_service"
            )
            
            # Cache for quick access
            data_point = MetricDataPoint(
                metric_name=metric_name,
                value=value,
                timestamp=datetime.now(timezone.utc),
                tags=metric_tags,
                service_name="telemetry_service"
            )
            
            if metric_name not in self._recent_metrics:
                self._recent_metrics[metric_name] = []
            
            self._recent_metrics[metric_name].append(data_point)
            
            # Trim cache
            if len(self._recent_metrics[metric_name]) > self._max_cached_metrics:
                self._recent_metrics[metric_name] = self._recent_metrics[metric_name][-self._max_cached_metrics:]
            
            return result.status == MemoryOpStatus.OK
            
        except Exception as e:
            logger.error(f"Failed to record metric {metric_name}: {e}")
            return False
    
    async def record_resource_usage(
        self, 
        service_name: str, 
        usage: ResourceUsage
    ) -> bool:
        """
        Record resource usage as multiple metrics in the graph.
        
        Each aspect of resource usage becomes a separate memory node,
        allowing for fine-grained introspection.
        """
        try:
            success = True
            
            # Record each resource metric separately
            if usage.tokens_used:
                success &= await self.record_metric(
                    f"{service_name}.tokens_used",
                    float(usage.tokens_used),
                    {"service": service_name, "resource_type": "tokens"}
                )
            
            if usage.tokens_input:
                success &= await self.record_metric(
                    f"{service_name}.tokens_input",
                    float(usage.tokens_input),
                    {"service": service_name, "resource_type": "tokens", "direction": "input"}
                )
            
            if usage.tokens_output:
                success &= await self.record_metric(
                    f"{service_name}.tokens_output",
                    float(usage.tokens_output),
                    {"service": service_name, "resource_type": "tokens", "direction": "output"}
                )
            
            if usage.cost_cents:
                success &= await self.record_metric(
                    f"{service_name}.cost_cents",
                    usage.cost_cents,
                    {"service": service_name, "resource_type": "cost", "unit": "cents"}
                )
            
            if usage.carbon_grams:
                success &= await self.record_metric(
                    f"{service_name}.carbon_grams",
                    usage.carbon_grams,
                    {"service": service_name, "resource_type": "carbon", "unit": "grams"}
                )
            
            if usage.compute_ms:
                success &= await self.record_metric(
                    f"{service_name}.compute_ms",
                    float(usage.compute_ms),
                    {"service": service_name, "resource_type": "compute", "unit": "milliseconds"}
                )
            
            if usage.memory_mb:
                success &= await self.record_metric(
                    f"{service_name}.memory_mb",
                    float(usage.memory_mb),
                    {"service": service_name, "resource_type": "memory", "unit": "megabytes"}
                )
            
            return success
            
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
        """
        Query metrics from the graph memory.
        
        This uses the MemoryService's recall_timeseries capability to
        retrieve historical metric data.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for metric queries")
                return []
            
            # Calculate hours from time range
            hours = 24  # Default
            if _time_range:
                start, end = _time_range
                hours = int((end - start).total_seconds() / 3600)
            
            # Recall time series data from memory
            timeseries_data = await self._memory_bus.recall_timeseries(
                scope="local",  # Operational metrics are in local scope
                hours=hours,
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="telemetry_service"
            )
            
            # Convert to MetricDataPoint objects
            results: List[MetricDataPoint] = []
            for data in timeseries_data:
                # Filter by metric names if specified
                if _metric_names and data.metric_name not in _metric_names:
                    continue
                
                # Filter by service names if specified
                if _service_names:
                    tags = data.tags or {}
                    if tags.get('service') not in _service_names:
                        continue
                
                # Filter by tags if specified
                if _tags:
                    data_tags = data.tags or {}
                    if not all(data_tags.get(k) == v for k, v in _tags.items()):
                        continue
                
                # Create MetricDataPoint
                if data.metric_name and data.value is not None:
                    results.append(MetricDataPoint(
                        metric_name=data.metric_name,
                        value=data.value,
                        timestamp=data.timestamp,
                        tags=data.tags or {},
                        service_name=(data.tags or {}).get('service')
                    ))
            
            # TODO: Implement aggregation if specified
            if _aggregation:
                logger.info(f"Aggregation '{_aggregation}' requested but not yet implemented")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to query metrics: {e}")
            return []
    
    async def get_service_status(
        self, 
        service_name: Optional[str] = None
    ) -> Union[ServiceStatus, Dict[str, ServiceStatus]]:
        """
        Get service status by analyzing recent metrics from the graph.
        
        This demonstrates the agent's ability to introspect its own
        operational state through the unified memory system.
        """
        try:
            if service_name:
                # Get status for specific service
                recent_metrics = self._recent_metrics.get(f"{service_name}.tokens_used", [])
                last_metric = recent_metrics[-1] if recent_metrics else None
                
                return ServiceStatus(
                    service_name=service_name,
                    status="healthy" if last_metric else "unknown",
                    uptime_seconds=None,  # TODO: Calculate from first metric
                    last_heartbeat=last_metric.timestamp if last_metric else None,
                    metrics={
                        "recent_tokens": last_metric.value if last_metric else 0.0
                    }
                )
            else:
                # Get status for all services
                all_status: Dict[str, ServiceStatus] = {}
                
                # Extract unique service names from cached metrics
                service_names = set()
                for metric_name in self._recent_metrics.keys():
                    if '.' in metric_name:
                        service_name = metric_name.split('.')[0]
                        service_names.add(service_name)
                
                for svc_name in service_names:
                    status = await self.get_service_status(svc_name)
                    if isinstance(status, ServiceStatus):
                        all_status[svc_name] = status
                
                return all_status
                
        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            if service_name:
                return ServiceStatus(
                    service_name=service_name,
                    status="error",
                    uptime_seconds=None,
                    last_heartbeat=None,
                    metrics={}
                )
            else:
                return {}
    
    async def get_resource_limits(self) -> ResourceLimits:
        """Get resource limits configuration."""
        return self._resource_limits
    
    async def start(self) -> None:
        """Start the telemetry service."""
        logger.info("GraphTelemetryService started - routing all metrics through memory graph")
    
    async def stop(self) -> None:
        """Stop the telemetry service."""
        # Store a final metric about service shutdown
        await self.record_metric(
            "telemetry_service.shutdown",
            1.0,
            {"event": "service_stop", "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        logger.info("GraphTelemetryService stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the telemetry service is healthy."""
        return self._memory_bus is not None
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "record_metric", "record_resource_usage", "query_metrics",
            "get_service_status", "get_resource_limits", "graph_storage"
        ]