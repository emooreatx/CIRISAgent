"""
Graph-based TelemetryService that stores all metrics as memories in the graph.

This implements the "Graph Memory as Identity Architecture" patent by routing
all telemetry data through the memory system as TSDBGraphNodes.

Consolidates functionality from:
- GraphTelemetryService (graph-based metrics)
- AdapterTelemetryService (system snapshots)
"""

import logging
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ciris_engine.protocols.services import GraphServiceProtocol as TelemetryServiceProtocol
from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.schemas.runtime.resources import ResourceUsage
from ciris_engine.schemas.runtime.protocols_core import MetricDataPoint, ServiceStatus, ResourceLimits
from ciris_engine.schemas.services.operations import MemoryOpStatus
from ciris_engine.schemas.runtime.system_context import SystemSnapshot
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, GraphNode, NodeType
from ciris_engine.schemas.services.graph.telemetry import (
    ProcessSnapshotResult, TelemetryData, ResourceData, BehavioralData,
    UserProfile, ChannelContext, ConsolidationResult, TelemetryServiceStatus,
    GraphQuery, ServiceCapabilities as TelemetryCapabilities
)
from ciris_engine.logic.buses.memory_bus import MemoryBus

logger = logging.getLogger(__name__)

class MemoryType(str, Enum):
    """Types of memories in the unified system."""
    OPERATIONAL = "operational"  # Metrics, logs, performance data
    BEHAVIORAL = "behavioral"    # Actions, decisions, patterns
    SOCIAL = "social"           # Interactions, relationships, gratitude
    IDENTITY = "identity"       # Self-knowledge, capabilities, values
    WISDOM = "wisdom"          # Learned principles, insights

class GracePolicy(str, Enum):
    """Policies for applying grace in memory consolidation."""
    FORGIVE_ERRORS = "forgive_errors"        # Consolidate errors into learning
    EXTEND_PATIENCE = "extend_patience"      # Allow more time before judging
    ASSUME_GOOD_INTENT = "assume_good_intent"  # Interpret ambiguity positively
    RECIPROCAL_GRACE = "reciprocal_grace"    # Mirror the grace we receive

@dataclass
class ConsolidationCandidate:
    """A set of memories that could be consolidated."""
    memory_ids: List[str]
    memory_type: MemoryType
    time_span: timedelta
    total_size: int
    grace_applicable: bool
    grace_reasons: List[str]

class GraphTelemetryService(TelemetryServiceProtocol, ServiceProtocol):
    """
    Consolidated TelemetryService that stores all metrics as graph memories.
    
    This service implements the vision where "everything is a memory" by
    converting telemetry data into TSDBGraphNodes stored in the memory graph.
    
    Features:
    - Processes SystemSnapshot data from adapters
    - Records operational metrics and resource usage
    - Stores behavioral, social, and identity context
    - Applies grace-based wisdom to memory consolidation
    """
    
    def __init__(
        self,
        memory_bus: Optional[MemoryBus] = None,
        time_service: Optional[Any] = None  # TimeServiceProtocol
    ) -> None:
        super().__init__()
        self._memory_bus = memory_bus
        self._time_service = time_service
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
        
        # Consolidation settings
    
    def _set_service_registry(self, registry: object) -> None:
        """Set the service registry for accessing memory bus and time service (internal method)."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            # Try to get memory bus from registry
            try:
                from ciris_engine.logic.buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
        
        # Get time service from registry if not provided
        if not self._time_service and registry:
            from ciris_engine.schemas.runtime.enums import ServiceType
            time_services = registry.get_all_by_type(ServiceType.TIME)
            if time_services:
                self._time_service = time_services[0].provider
    
    def _now(self) -> datetime:
        """Get current time from time service."""
        if not self._time_service:
            raise RuntimeError("FATAL: TimeService not available! This is a critical system failure.")
        return self._time_service.now()
    
    async def record_metric(
        self, 
        metric_name: str, 
        value: float = 1.0, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a metric by storing it as a memory in the graph.
        
        This creates a TSDBGraphNode and stores it via the MemoryService,
        implementing the unified telemetry flow.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for telemetry storage")
                return
            
            # Add standard telemetry tags
            metric_tags = tags or {}
            metric_tags.update({
                "source": "telemetry",
                "metric_type": "operational",
                "timestamp": self._now().isoformat()
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
                timestamp=self._now(),
                tags=metric_tags,
                service_name="telemetry_service"
            )
            
            if metric_name not in self._recent_metrics:
                self._recent_metrics[metric_name] = []
            
            self._recent_metrics[metric_name].append(data_point)
            
            # Trim cache
            if len(self._recent_metrics[metric_name]) > self._max_cached_metrics:
                self._recent_metrics[metric_name] = self._recent_metrics[metric_name][-self._max_cached_metrics:]
            
            if result.status != MemoryOpStatus.OK:
                logger.error(f"Failed to store metric: {result}")
            
        except Exception as e:
            logger.error(f"Failed to record metric {metric_name}: {e}")
    
    async def _record_resource_usage(
        self, 
        service_name: str, 
        usage: ResourceUsage
    ) -> None:
        """
        Record resource usage as multiple metrics in the graph (internal method).
        
        Each aspect of resource usage becomes a separate memory node,
        allowing for fine-grained introspection.
        """
        try:
            # Record each resource metric separately
            if usage.tokens_used:
                await self.record_metric(
                    f"{service_name}.tokens_used",
                    float(usage.tokens_used),
                    {"service": service_name, "resource_type": "tokens"}
                )
            
            if usage.tokens_input:
                await self.record_metric(
                    f"{service_name}.tokens_input",
                    float(usage.tokens_input),
                    {"service": service_name, "resource_type": "tokens", "direction": "input"}
                )
            
            if usage.tokens_output:
                await self.record_metric(
                    f"{service_name}.tokens_output",
                    float(usage.tokens_output),
                    {"service": service_name, "resource_type": "tokens", "direction": "output"}
                )
            
            if usage.cost_cents:
                await self.record_metric(
                    f"{service_name}.cost_cents",
                    usage.cost_cents,
                    {"service": service_name, "resource_type": "cost", "unit": "cents"}
                )
            
            if usage.carbon_grams:
                await self.record_metric(
                    f"{service_name}.carbon_grams",
                    usage.carbon_grams,
                    {"service": service_name, "resource_type": "carbon", "unit": "grams"}
                )
            
            if usage.compute_ms:
                await self.record_metric(
                    f"{service_name}.compute_ms",
                    float(usage.compute_ms),
                    {"service": service_name, "resource_type": "compute", "unit": "milliseconds"}
                )
            
            if usage.memory_mb:
                await self.record_metric(
                    f"{service_name}.memory_mb",
                    float(usage.memory_mb),
                    {"service": service_name, "resource_type": "memory", "unit": "megabytes"}
                )
            
        except Exception as e:
            logger.error(f"Failed to record resource usage for {service_name}: {e}")
    
    async def query_metrics(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Union[str, float, datetime, Dict[str, str]]]]:
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
            if start_time and end_time:
                hours = int((end_time - start_time).total_seconds() / 3600)
            elif start_time:
                hours = int((self._now() - start_time).total_seconds() / 3600)
            
            # Recall time series data from memory
            timeseries_data = await self._memory_bus.recall_timeseries(
                scope="local",  # Operational metrics are in local scope
                hours=hours,
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="telemetry_service"
            )
            
            # Convert to dict format
            results: List[Dict[str, Union[str, float, datetime, Dict[str, str]]]] = []
            for data in timeseries_data:
                # Filter by metric name
                if data.metric_name != metric_name:
                    continue
                
                # Filter by tags if specified
                if tags:
                    data_tags = data.tags or {}
                    if not all(data_tags.get(k) == v for k, v in tags.items()):
                        continue
                
                # Filter by time range
                if data.timestamp:
                    ts = datetime.fromisoformat(data.timestamp) if isinstance(data.timestamp, str) else data.timestamp
                    if start_time and ts < start_time:
                        continue
                    if end_time and ts > end_time:
                        continue
                
                # Create result dict
                if data.metric_name and data.value is not None:
                    results.append({
                        "metric_name": data.metric_name,
                        "value": data.value,
                        "timestamp": data.timestamp,
                        "tags": data.tags or {}
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to query metrics: {e}")
            return []
    
    async def get_metric_summary(self, metric_name: str, window_minutes: int = 60) -> Dict[str, float]:
        """Get metric summary statistics."""
        try:
            # Calculate time window
            end_time = self._now()
            start_time = end_time - timedelta(minutes=window_minutes)
            
            # Query metrics for the window
            metrics = await self.query_metrics(
                metric_name=metric_name,
                start_time=start_time,
                end_time=end_time
            )
            
            if not metrics:
                return {
                    "count": 0.0,
                    "sum": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "avg": 0.0
                }
            
            # Calculate summary statistics
            values = [m["value"] for m in metrics if isinstance(m["value"], (int, float))]
            
            return {
                "count": float(len(values)),
                "sum": float(sum(values)),
                "min": float(min(values)) if values else 0.0,
                "max": float(max(values)) if values else 0.0,
                "avg": float(sum(values) / len(values)) if values else 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to get metric summary for {metric_name}: {e}")
            return {
                "count": 0.0,
                "sum": 0.0,
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0
            }
    
    async def _get_service_status(
        self, 
        service_name: Optional[str] = None
    ) -> Union[ServiceStatus, Dict[str, ServiceStatus]]:
        """
        Get service status by analyzing recent metrics from the graph (internal method).
        
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
                    status = await self._get_service_status(svc_name)
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
    
    async def _get_resource_limits(self) -> ResourceLimits:
        """Get resource limits configuration (internal method)."""
        return self._resource_limits
    
    async def _process_system_snapshot(
        self,
        snapshot: SystemSnapshot,
        thought_id: str,
        task_id: Optional[str] = None
    ) -> ProcessSnapshotResult:
        """
        Process a SystemSnapshot and convert it to graph memories (internal method).
        
        This is the main entry point for the unified telemetry flow from adapters.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for telemetry storage")
                return ProcessSnapshotResult(error="Memory bus not available")
            
            results = ProcessSnapshotResult()
            
            # 1. Store operational metrics
            if snapshot.telemetry:
                await self._store_telemetry_metrics(snapshot.telemetry, thought_id, task_id)
                results.memories_created += 1
            
            # 2. Store resource usage
            if snapshot.current_round_resources:
                await self._store_resource_usage(snapshot.current_round_resources, thought_id, task_id)
                results.memories_created += 1
            
            # 3. Store behavioral data (task/thought summaries)
            if snapshot.current_task_details:
                await self._store_behavioral_data(snapshot.current_task_details, "task", thought_id)
                results.memories_created += 1
                
            if snapshot.current_thought_summary:
                await self._store_behavioral_data(snapshot.current_thought_summary, "thought", thought_id)
                results.memories_created += 1
            
            # 4. Store social context (user profiles, channel info)
            if snapshot.user_profiles:
                await self._store_social_context(snapshot.user_profiles, snapshot.channel_context, thought_id)
                results.memories_created += 1
            
            # 5. Store identity context
            if snapshot.agent_name or snapshot.wisdom_request:
                await self._store_identity_context(snapshot, thought_id)
                results.memories_created += 1
            
            # Consolidation is now handled by TSDBConsolidationService
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process system snapshot: {e}")
            return ProcessSnapshotResult(error=str(e))
    
    async def _store_telemetry_metrics(
        self,
        telemetry: TelemetryData,
        thought_id: str,
        task_id: Optional[str]
    ) -> None:
        """Store telemetry data as operational memories."""
        # Process metrics
        for key, value in telemetry.metrics.items():
            await self.record_metric(
                f"telemetry.{key}",
                float(value),
                {
                    "thought_id": thought_id,
                    "task_id": task_id or "",
                    "memory_type": MemoryType.OPERATIONAL.value
                }
            )
        
        # Process events
        for key, value in telemetry.events.items():
            await self.record_metric(
                f"telemetry.event.{key}",
                1.0,  # Event occurrence
                {
                    "thought_id": thought_id,
                    "task_id": task_id or "",
                    "memory_type": MemoryType.OPERATIONAL.value,
                    "event_value": value
                }
            )
    
    async def _store_resource_usage(
        self,
        resources: ResourceData,
        thought_id: str,
        task_id: Optional[str]
    ) -> None:
        """Store resource usage as operational memories."""
        if resources.llm:
            usage = ResourceUsage(**resources.llm)
            await self._record_resource_usage("llm_service", usage)
    
    async def _store_behavioral_data(
        self,
        data: BehavioralData,
        data_type: str,
        thought_id: str
    ) -> None:
        """Store behavioral data (tasks/thoughts) as memories."""
        node = GraphNode(
            id=f"behavioral_{thought_id}_{data_type}",
            type=NodeType.BEHAVIORAL,
            attributes={
                "data_type": data.data_type,
                "thought_id": thought_id,
                "content": data.content,
                "metadata": data.metadata,
                "memory_type": MemoryType.BEHAVIORAL.value
            },
            tags={
                "thought_id": thought_id,
                "data_type": data_type
            }
        )
        
        await self._memory_bus.memorize(
            node=node,
            handler_name="telemetry_service",
            metadata={"behavioral": True}
        )
    
    async def _store_social_context(
        self,
        user_profiles: List[UserProfile],
        channel_context: Optional[ChannelContext],
        thought_id: str
    ) -> None:
        """Store social context as memories."""
        node = GraphNode(
            id=f"social_{thought_id}",
            type=NodeType.SOCIAL,
            attributes={
                "user_profiles": [p.dict() for p in user_profiles],
                "channel_context": channel_context.dict() if channel_context else None,
                "memory_type": MemoryType.SOCIAL.value
            },
            tags={
                "thought_id": thought_id,
                "user_count": str(len(user_profiles))
            }
        )
        
        await self._memory_bus.memorize(
            node=node,
            handler_name="telemetry_service",
            metadata={"social": True}
        )
    
    async def _store_identity_context(
        self,
        snapshot: SystemSnapshot,
        thought_id: str
    ) -> None:
        """Store identity-related context as memories."""
        node = GraphNode(
            id=f"identity_{thought_id}",
            type=NodeType.IDENTITY,
            attributes={
                "agent_name": snapshot.agent_name,
                "wisdom_request": snapshot.wisdom_request,
                "memory_type": MemoryType.IDENTITY.value
            },
            tags={
                "thought_id": thought_id,
                "has_wisdom": str(bool(snapshot.wisdom_request))
            }
        )
        
        await self._memory_bus.memorize(
            node=node,
            handler_name="telemetry_service",
            metadata={"identity": True}
        )
    
    
    async def start(self) -> None:
        """Start the telemetry service."""
        logger.info("GraphTelemetryService started - routing all metrics through memory graph")
    
    async def stop(self) -> None:
        """Stop the telemetry service."""
        # Store a final metric about service shutdown
        await self.record_metric(
            "telemetry_service.shutdown",
            1.0,
            {"event": "service_stop", "timestamp": self._now().isoformat()}
        )
        logger.info("GraphTelemetryService stopped")
    
    def get_status(self) -> TelemetryServiceStatus:
        """Get service status."""
        return TelemetryServiceStatus(
            healthy=self._memory_bus is not None,
            cached_metrics=sum(len(metrics) for metrics in self._recent_metrics.values()),
            metric_types=list(self._recent_metrics.keys()),
            memory_bus_available=self._memory_bus is not None,
            last_consolidation=None  # Consolidation handled by TSDBConsolidationService
        )
    
    async def store_in_graph(self, node: GraphNode) -> str:
        """Store a node in the graph - delegates to memory bus."""
        if not self._memory_bus:
            raise RuntimeError("Memory bus not available")
        result = await self._memory_bus.memorize(node)
        return node.id if result.status == MemoryOpStatus.OK else ""
    
    async def query_graph(self, query: GraphQuery) -> List[GraphNode]:
        """Query the graph - delegates to memory bus."""
        if not self._memory_bus:
            return []
        # Convert to timeseries query
        hours = query.hours
        return await self._memory_bus.recall_timeseries(
            scope="local",
            hours=hours,
            correlation_types=["METRIC_DATAPOINT"]
        )
    
    def get_node_type(self) -> str:
        """Get the type of nodes this service manages."""
        return "TELEMETRY"
    
    def get_capabilities(self) -> TelemetryCapabilities:
        """Return capabilities this service supports."""
        return TelemetryCapabilities(
            actions=[
                "record_metric", "record_resource_usage", "query_metrics",
                "get_service_status", "get_resource_limits", "process_system_snapshot"
            ],
            features=["graph_storage", "time_series_aggregation", "memory_consolidation", "grace_policies"],
            node_type="TELEMETRY"
        )
    
    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._memory_bus is not None and self._time_service is not None