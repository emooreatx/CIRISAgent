"""
Tiered metric collection system for CIRIS Agent telemetry.

Provides collectors with different intervals and security validation levels
to balance observability with performance and security constraints.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .security import SecurityFilter

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Enhanced metric data structure with hot/cold path awareness."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    path_type: str = "unknown"  # hot, cold, critical
    telemetry_required: bool = False
    source_module: Optional[str] = None
    line_number: Optional[int] = None
    
    
class BaseCollector(ABC):
    """Base class for all metric collectors."""
    
    def __init__(
        self,
        interval_ms: int,
        security_filter: Optional[SecurityFilter] = None,
        max_metrics_per_interval: int = 100
    ) -> None:
        self.interval_ms = interval_ms
        self.security_filter = security_filter or SecurityFilter()
        self.max_metrics_per_interval = max_metrics_per_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._metrics_collected = 0
        self._last_collection = datetime.now(timezone.utc)
        
    async def start(self) -> None:
        """Start the collector."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._collection_loop())
        logger.info(f"{self.__class__.__name__} started with {self.interval_ms}ms interval")
        
    async def stop(self) -> None:
        """Stop the collector."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"{self.__class__.__name__} stopped")
        
    async def _collection_loop(self) -> None:
        """Main collection loop."""
        while self._running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.interval_ms / 1000.0)
            except Exception as e:
                logger.error(f"Error in {self.__class__.__name__} collection: {e}")
                await asyncio.sleep(1.0)  # Back off on errors
                
    async def _collect_metrics(self) -> None:
        """Collect metrics with security validation."""
        try:
            raw_metrics = await self.collect_raw_metrics()
            if not raw_metrics:
                return
                
            if len(raw_metrics) > self.max_metrics_per_interval:
                logger.warning(
                    f"{self.__class__.__name__} exceeded max metrics per interval: "
                    f"{len(raw_metrics)} > {self.max_metrics_per_interval}"
                )
                raw_metrics = raw_metrics[:self.max_metrics_per_interval]
                
            filtered_metrics = []
            for metric in raw_metrics:
                filtered_metric = self.security_filter.sanitize(metric.name, metric.value)
                if filtered_metric:
                    filtered_metrics.append(MetricData(
                        name=filtered_metric[0],
                        value=filtered_metric[1],
                        timestamp=metric.timestamp,
                        tags=metric.tags
                    ))
                    
            if filtered_metrics:
                await self.process_metrics(filtered_metrics)
                self._metrics_collected += len(filtered_metrics)
                self._last_collection = datetime.now(timezone.utc)
                
        except Exception as e:
            logger.error(f"Error collecting metrics in {self.__class__.__name__}: {e}")
            
    @abstractmethod
    async def collect_raw_metrics(self) -> List[MetricData]:
        """Collect raw metrics. Override in subclasses."""
        
    @abstractmethod
    async def process_metrics(self, metrics: List[MetricData]) -> None:
        """Process filtered metrics. Override in subclasses."""
        
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            "collector_type": self.__class__.__name__,
            "interval_ms": self.interval_ms,
            "metrics_collected": self._metrics_collected,
            "last_collection": self._last_collection.isoformat(),
            "running": self._running
        }


class InstantCollector(BaseCollector):
    """
    Instant collector for critical HOT PATH metrics (50ms interval).
    Used for circuit breakers, critical errors, and security/auth events.
    All metrics from this collector are considered HOT PATH.
    """
    
    def __init__(
        self,
        telemetry_service: Optional[Any] = None,
        circuit_breaker_registry: Optional[Any] = None
    ) -> None:
        super().__init__(interval_ms=50, max_metrics_per_interval=10)
        self.telemetry_service = telemetry_service
        self.circuit_breaker_registry = circuit_breaker_registry
        
    async def collect_raw_metrics(self) -> List[MetricData]:
        """Collect critical instant metrics."""
        metrics = []
        now = datetime.now(timezone.utc)
        
        if self.circuit_breaker_registry:
            try:
                for name, breaker in getattr(self.circuit_breaker_registry, '_breakers', {}).items():
                    state = getattr(breaker, 'state', 'unknown')
                    metrics.append(MetricData(
                        name=f"circuit_breaker_{name}_state",
                        value=1.0 if state == 'open' else 0.0,
                        timestamp=now,
                        tags={"breaker": name, "state": state, "priority": "critical"},
                        path_type="hot",
                        telemetry_required=True,
                        source_module="circuit_breaker_registry"
                    ))
            except Exception as e:
                logger.debug(f"Error collecting circuit breaker metrics: {e}")
                
        return metrics
        
    async def process_metrics(self, metrics: List[MetricData]) -> None:
        """Process instant metrics."""
        if self.telemetry_service:
            for metric in metrics:
                await self.telemetry_service.record_metric(metric.name, metric.value)


class FastCollector(BaseCollector):
    """
    Fast collector for active HOT PATH system metrics (250ms interval).
    Used for active thoughts, handler selection, and DMA execution.
    These are HOT paths that directly affect agent responsiveness.
    """
    
    def __init__(
        self,
        telemetry_service: Optional[Any] = None,
        thought_manager: Optional[Any] = None
    ) -> None:
        super().__init__(interval_ms=250, max_metrics_per_interval=20)
        self.telemetry_service = telemetry_service
        self.thought_manager = thought_manager
        
    async def collect_raw_metrics(self) -> List[MetricData]:
        """Collect fast metrics."""
        metrics = []
        now = datetime.now(timezone.utc)
        
        if self.thought_manager:
            try:
                active_count = getattr(self.thought_manager, 'active_thoughts_count', 0)
                metrics.append(MetricData(
                    name="thoughts_active_count",
                    value=float(active_count),
                    timestamp=now,
                    tags={"component": "thought_manager", "priority": "high"},
                    path_type="hot",
                    telemetry_required=True,
                    source_module="thought_manager"
                ))
            except Exception as e:
                logger.debug(f"Error collecting thought metrics: {e}")
                
        return metrics
        
    async def process_metrics(self, metrics: List[MetricData]) -> None:
        """Process fast metrics."""
        if self.telemetry_service:
            for metric in metrics:
                await self.telemetry_service.record_metric(metric.name, metric.value)


class NormalCollector(BaseCollector):
    """
    Normal collector for standard metrics (1s interval).
    Used for resource usage and guardrails.
    """
    
    def __init__(
        self,
        telemetry_service: Optional[Any] = None,
        resource_monitor: Optional[Any] = None
    ) -> None:
        super().__init__(interval_ms=1000, max_metrics_per_interval=50)
        self.telemetry_service = telemetry_service
        self.resource_monitor = resource_monitor
        
    async def collect_raw_metrics(self) -> List[MetricData]:
        """Collect normal interval metrics."""
        metrics = []
        now = datetime.now(timezone.utc)
        
        if self.resource_monitor:
            try:
                memory_mb = getattr(self.resource_monitor, 'current_memory_mb', 0)
                cpu_percent = getattr(self.resource_monitor, 'current_cpu_percent', 0.0)
                
                metrics.extend([
                    MetricData(
                        name="resource_memory_mb",
                        value=float(memory_mb),
                        timestamp=now,
                        tags={"resource": "memory"}
                    ),
                    MetricData(
                        name="resource_cpu_percent",
                        value=float(cpu_percent),
                        timestamp=now,
                        tags={"resource": "cpu"}
                    )
                ])
            except Exception as e:
                logger.debug(f"Error collecting resource metrics: {e}")
                
        return metrics
        
    async def process_metrics(self, metrics: List[MetricData]) -> None:
        """Process normal metrics."""
        if self.telemetry_service:
            for metric in metrics:
                await self.telemetry_service.record_metric(metric.name, metric.value)


class SlowCollector(BaseCollector):
    """
    Slow collector for COLD PATH expensive metrics (5s interval).
    Used for memory operations, persistence, and context fetches.
    These are COLD paths accessed via service registry or persistence.
    """
    
    def __init__(
        self,
        telemetry_service: Optional[Any] = None,
        memory_service: Optional[Any] = None
    ) -> None:
        super().__init__(interval_ms=5000, max_metrics_per_interval=30)
        self.telemetry_service = telemetry_service
        self.memory_service = memory_service
        
    async def collect_raw_metrics(self) -> List[MetricData]:
        """Collect slow interval metrics."""
        metrics = []
        now = datetime.now(timezone.utc)
        
        if self.memory_service:
            try:
                ops_count = getattr(self.memory_service, 'operations_count', 0)
                metrics.append(MetricData(
                    name="memory_operations_total",
                    value=float(ops_count),
                    timestamp=now,
                    tags={"component": "memory_service", "priority": "low"},
                    path_type="cold",
                    telemetry_required=False,
                    source_module="memory_service"
                ))
            except Exception as e:
                logger.debug(f"Error collecting memory service metrics: {e}")
                
        return metrics
        
    async def process_metrics(self, metrics: List[MetricData]) -> None:
        """Process slow metrics with extra sanitization."""
        if self.telemetry_service:
            for metric in metrics:
                # Extra security check for slow metrics
                if not metric.name.startswith(('memory_', 'dma_', 'resource_')):
                    logger.warning(f"Unexpected metric in SlowCollector: {metric.name}")
                    continue
                await self.telemetry_service.record_metric(metric.name, metric.value)


class AggregateCollector(BaseCollector):
    """
    Aggregate collector for rollup metrics (30s interval).
    Used for community metrics and data aggregation with full audit.
    """
    
    def __init__(
        self,
        telemetry_service: Optional[Any] = None,
        audit_service: Optional[Any] = None
    ) -> None:
        super().__init__(interval_ms=30000, max_metrics_per_interval=100)
        self.telemetry_service = telemetry_service
        self.audit_service = audit_service
        
    async def collect_raw_metrics(self) -> List[MetricData]:
        """Collect aggregate metrics."""
        metrics = []
        now = datetime.now(timezone.utc)
        
        if self.telemetry_service:
            try:
                cutoff = now - timedelta(seconds=30)
                history = getattr(self.telemetry_service, '_history', {})
                
                for metric_name, records in history.items():
                    recent_records = [r for r in records if r[0] > cutoff]
                    if recent_records:
                        total = sum(r[1] for r in recent_records)
                        avg = total / len(recent_records)
                        
                        metrics.append(MetricData(
                            name=f"{metric_name}_30s_avg",
                            value=avg,
                            timestamp=now,
                            tags={"aggregation": "30s_average", "source": metric_name}
                        ))
                        
            except Exception as e:
                logger.debug(f"Error collecting aggregate metrics: {e}")
                
        return metrics
        
    async def process_metrics(self, metrics: List[MetricData]) -> None:
        """Process aggregate metrics with audit logging."""
        if self.audit_service:
            # Audit aggregate metric collection
            await self.audit_service.log_action(
                "telemetry_aggregation",
                {"metrics_count": len(metrics), "timestamp": datetime.now(timezone.utc).isoformat()},
                "success"
            )
            
        if self.telemetry_service:
            for metric in metrics:
                await self.telemetry_service.record_metric(metric.name, metric.value)


class CollectorManager:
    """Manages all telemetry collectors."""
    
    def __init__(self, telemetry_service: Optional[Any] = None) -> None:
        self.telemetry_service = telemetry_service
        self.collectors: Dict[str, BaseCollector] = {}
        
    def add_collector(self, name: str, collector: BaseCollector) -> None:
        """Add a collector to the manager."""
        self.collectors[name] = collector
        
    async def start_all(self) -> None:
        """Start all collectors."""
        for name, collector in self.collectors.items():
            try:
                await collector.start()
                logger.info(f"Started collector: {name}")
            except Exception as e:
                logger.error(f"Failed to start collector {name}: {e}")
                
    async def stop_all(self) -> None:
        """Stop all collectors."""
        for name, collector in self.collectors.items():
            try:
                await collector.stop()
                logger.info(f"Stopped collector: {name}")
            except Exception as e:
                logger.error(f"Failed to stop collector {name}: {e}")
                
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all collectors."""
        return {
            name: collector.get_stats()
            for name, collector in self.collectors.items()
        }