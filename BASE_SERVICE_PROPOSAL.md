# Base Service Class Proposal for CIRIS

## Executive Summary

After analyzing all 19 services in the CIRIS codebase, I propose creating a unified `BaseService` class that consolidates common patterns while maintaining flexibility for service-specific needs. This will replace the existing fragmented base classes and provide a single, clear foundation for all services.

## Current State Analysis

### Existing Base Classes
1. **Service** (from `ciris_engine.logic.adapters.base`) - Provides retry logic
2. **BaseGraphService** - Abstract base for graph services with memory bus integration
3. **Direct Protocol Implementation** - Some services implement protocols directly

### Common Patterns Identified

#### 1. Initialization Pattern
```python
def __init__(self, ...dependencies...):
    self._started = False
    self._start_time = None  # For uptime tracking
    self.service_name = self.__class__.__name__
    # Store dependencies
    self._time_service = time_service
    # Initialize state tracking
    self._metrics = {}
    self._last_error = None
```

#### 2. Lifecycle Management
```python
async def start(self) -> None:
    self._started = True
    self._start_time = self._time_service.now() if self._time_service else datetime.now(timezone.utc)
    logger.info(f"{self.service_name} started")

async def stop(self) -> None:
    self._started = False
    # Cleanup resources
    logger.info(f"{self.service_name} stopped")
```

#### 3. Health Checking
```python
async def is_healthy(self) -> bool:
    return self._started and self._check_dependencies()
```

#### 4. Status Reporting
```python
def get_status(self) -> ServiceStatus:
    uptime = self._calculate_uptime()
    return ServiceStatus(
        service_name=self.service_name,
        service_type=self._get_service_type(),
        is_healthy=self._started,
        uptime_seconds=uptime,
        metrics=self._collect_metrics(),
        last_error=self._last_error,
        last_health_check=self._time_service.now()
    )
```

#### 5. Capabilities Declaration
```python
def get_capabilities(self) -> ServiceCapabilities:
    return ServiceCapabilities(
        service_name=self.service_name,
        actions=self._get_actions(),
        version=self._get_version(),
        dependencies=self._get_dependencies(),
        metadata=self._get_metadata()
    )
```

## Proposed Base Service Class

```python
"""
Base Service Class for CIRIS - Maximum clarity and simplicity.

Design Principles:
1. No Dicts, No Strings, No Kings - All typed with Pydantic
2. Clear separation between required and optional functionality
3. Dependency injection for all external services
4. Comprehensive lifecycle management
5. Built-in observability (metrics, health, status)
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
import logging

from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.runtime.enums import ServiceType


class BaseService(ABC, ServiceProtocol):
    """
    Base class for all CIRIS services.
    
    Provides:
    - Lifecycle management (start/stop)
    - Health checking
    - Status reporting
    - Metrics collection
    - Dependency tracking
    - Error tracking
    
    Subclasses MUST implement:
    - get_service_type() -> ServiceType
    - _get_actions() -> List[str]
    - _check_dependencies() -> bool
    
    Subclasses MAY override:
    - _on_start() -> None (for custom startup logic)
    - _on_stop() -> None (for custom cleanup)
    - _collect_custom_metrics() -> Dict[str, float]
    - _get_metadata() -> Dict[str, Any]
    """
    
    def __init__(
        self,
        *,  # Force keyword-only arguments for clarity
        time_service: Optional[TimeServiceProtocol] = None,
        service_name: Optional[str] = None,
        version: str = "1.0.0"
    ) -> None:
        """
        Initialize base service.
        
        Args:
            time_service: Time service for consistent timestamps (optional)
            service_name: Override service name (defaults to class name)
            version: Service version string
        """
        # Core state
        self._started = False
        self._start_time: Optional[datetime] = None
        self.service_name = service_name or self.__class__.__name__
        self._version = version
        
        # Dependencies
        self._time_service = time_service
        self._logger = logging.getLogger(f"ciris_engine.services.{self.service_name}")
        
        # Metrics and observability
        self._metrics: Dict[str, float] = {}
        self._last_error: Optional[str] = None
        self._last_health_check: Optional[datetime] = None
        self._request_count = 0
        self._error_count = 0
        
        # Dependency tracking
        self._dependencies: Set[str] = set()
        self._register_dependencies()
    
    # Required abstract methods
    
    @abstractmethod
    def get_service_type(self) -> ServiceType:
        """Get the service type enum value."""
        ...
    
    @abstractmethod
    def _get_actions(self) -> List[str]:
        """Get list of actions this service provides."""
        ...
    
    @abstractmethod
    def _check_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        ...
    
    # Optional override points
    
    async def _on_start(self) -> None:
        """Custom startup logic - override in subclass if needed."""
        pass
    
    async def _on_stop(self) -> None:
        """Custom cleanup logic - override in subclass if needed."""
        pass
    
    def _collect_custom_metrics(self) -> Dict[str, float]:
        """Collect service-specific metrics - override in subclass."""
        return {}
    
    def _get_metadata(self) -> Dict[str, Any]:
        """Get service-specific metadata - override in subclass."""
        return {}
    
    def _register_dependencies(self) -> None:
        """Register service dependencies - override in subclass."""
        if self._time_service:
            self._dependencies.add("TimeService")
    
    # ServiceProtocol implementation
    
    async def start(self) -> None:
        """Start the service."""
        if self._started:
            self._logger.warning(f"{self.service_name} already started")
            return
        
        try:
            # Check dependencies first
            if not self._check_dependencies():
                raise RuntimeError(f"{self.service_name}: Required dependencies not available")
            
            # Set start time
            self._start_time = self._now()
            
            # Call custom startup logic
            await self._on_start()
            
            # Mark as started
            self._started = True
            self._logger.info(f"{self.service_name} started successfully")
            
        except Exception as e:
            self._last_error = str(e)
            self._logger.error(f"{self.service_name} failed to start: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the service."""
        if not self._started:
            self._logger.warning(f"{self.service_name} not started")
            return
        
        try:
            # Call custom cleanup logic
            await self._on_stop()
            
            # Mark as stopped
            self._started = False
            self._logger.info(f"{self.service_name} stopped successfully")
            
        except Exception as e:
            self._last_error = str(e)
            self._logger.error(f"{self.service_name} error during stop: {e}")
            raise
    
    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        self._last_health_check = self._now()
        return self._started and self._check_dependencies()
    
    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name=self.service_name,
            actions=self._get_actions(),
            version=self._version,
            dependencies=list(self._dependencies),
            metadata=self._get_metadata()
        )
    
    def get_status(self) -> ServiceStatus:
        """Get current service status."""
        return ServiceStatus(
            service_name=self.service_name,
            service_type=self.get_service_type().value,
            is_healthy=self._started and self._check_dependencies(),
            uptime_seconds=self._calculate_uptime(),
            metrics=self._collect_metrics(),
            last_error=self._last_error,
            last_health_check=self._last_health_check
        )
    
    # Helper methods
    
    def _now(self) -> datetime:
        """Get current time using time service if available."""
        if self._time_service:
            return self._time_service.now()
        return datetime.now(timezone.utc)
    
    def _calculate_uptime(self) -> float:
        """Calculate service uptime in seconds."""
        if not self._started or not self._start_time:
            return 0.0
        return (self._now() - self._start_time).total_seconds()
    
    def _collect_metrics(self) -> Dict[str, float]:
        """Collect all metrics including custom ones."""
        base_metrics = {
            "uptime_seconds": self._calculate_uptime(),
            "request_count": float(self._request_count),
            "error_count": float(self._error_count),
            "error_rate": float(self._error_count) / max(1, self._request_count),
            "healthy": 1.0 if self._started else 0.0,
        }
        
        # Add custom metrics
        custom_metrics = self._collect_custom_metrics()
        base_metrics.update(custom_metrics)
        
        return base_metrics
    
    # Request tracking helpers (for services that handle requests)
    
    def _track_request(self) -> None:
        """Track a request for metrics."""
        self._request_count += 1
    
    def _track_error(self, error: Exception) -> None:
        """Track an error for metrics."""
        self._error_count += 1
        self._last_error = str(error)
        self._logger.error(f"{self.service_name} error: {error}")
```

## Specialized Base Classes

### 1. BaseGraphService (Enhanced)
```python
class BaseGraphService(BaseService):
    """Base class for graph services with memory bus integration."""
    
    def __init__(
        self,
        *,
        memory_bus: Optional['MemoryBus'] = None,
        **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._memory_bus = memory_bus
    
    def _register_dependencies(self) -> None:
        super()._register_dependencies()
        self._dependencies.add("MemoryBus")
    
    def _check_dependencies(self) -> bool:
        return self._memory_bus is not None
    
    def _collect_custom_metrics(self) -> Dict[str, float]:
        return {
            "memory_bus_available": 1.0 if self._memory_bus else 0.0
        }
    
    # Graph-specific methods
    async def store_in_graph(self, node: GraphNode) -> str:
        """Store node in graph via memory bus."""
        ...
    
    async def query_graph(self, query: MemoryQuery) -> List[GraphNode]:
        """Query graph via memory bus."""
        ...
```

### 2. BaseInfrastructureService
```python
class BaseInfrastructureService(BaseService):
    """Base class for infrastructure services."""
    
    def get_service_type(self) -> ServiceType:
        return ServiceType.INFRASTRUCTURE
    
    def _get_metadata(self) -> Dict[str, Any]:
        return {
            "category": "infrastructure",
            "critical": True
        }
```

### 3. BaseScheduledService
```python
class BaseScheduledService(BaseService):
    """Base class for services with scheduled tasks."""
    
    def __init__(
        self,
        *,
        run_interval_seconds: float = 60.0,
        **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._run_interval = run_interval_seconds
        self._task: Optional[asyncio.Task] = None
    
    async def _on_start(self) -> None:
        """Start the scheduled task."""
        self._task = asyncio.create_task(self._run_loop())
    
    async def _on_stop(self) -> None:
        """Stop the scheduled task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run_loop(self) -> None:
        """Main scheduled task loop."""
        while self._started:
            try:
                await self._run_scheduled_task()
            except Exception as e:
                self._track_error(e)
            
            await asyncio.sleep(self._run_interval)
    
    @abstractmethod
    async def _run_scheduled_task(self) -> None:
        """Execute the scheduled task - must be implemented."""
        ...
```

## Migration Strategy

### Phase 1: Create Base Classes
1. Implement `BaseService` in `ciris_engine/logic/services/base_service.py`
2. Implement specialized base classes
3. Add comprehensive tests

### Phase 2: Migrate Simple Services
Start with services that have minimal dependencies:
- TimeService
- ShutdownService
- ResourceMonitorService

### Phase 3: Migrate Graph Services
Update all graph services to use enhanced `BaseGraphService`:
- LocalGraphMemoryService
- GraphAuditService
- GraphConfigService
- GraphTelemetryService
- IncidentManagementService
- TSDBConsolidationService

### Phase 4: Migrate Complex Services
Update remaining services:
- LLMService (with circuit breaker)
- WiseAuthorityService
- RuntimeControlService
- Special services (SelfObservation, AdaptiveFilter, TaskScheduler)

## Benefits

1. **Consistency**: All services follow the same patterns
2. **Simplicity**: Clear base class with well-defined extension points
3. **Observability**: Built-in metrics, health checks, and status reporting
4. **Type Safety**: No dicts, full Pydantic integration
5. **Maintainability**: Single source of truth for common functionality
6. **Testability**: Easy to mock and test with clear interfaces

## Example Implementation

```python
class MyCustomService(BaseService):
    """Example service implementation."""
    
    def __init__(
        self,
        *,
        time_service: TimeServiceProtocol,
        my_dependency: MyDependencyProtocol,
        **kwargs: Any
    ) -> None:
        super().__init__(time_service=time_service, **kwargs)
        self._my_dependency = my_dependency
    
    def get_service_type(self) -> ServiceType:
        return ServiceType.CORE
    
    def _get_actions(self) -> List[str]:
        return ["process_data", "validate_input", "generate_report"]
    
    def _check_dependencies(self) -> bool:
        return self._my_dependency is not None
    
    def _register_dependencies(self) -> None:
        super()._register_dependencies()
        self._dependencies.add("MyDependency")
    
    async def _on_start(self) -> None:
        """Initialize connections or resources."""
        await self._my_dependency.connect()
    
    async def _on_stop(self) -> None:
        """Cleanup connections or resources."""
        await self._my_dependency.disconnect()
    
    def _collect_custom_metrics(self) -> Dict[str, float]:
        return {
            "queue_size": float(self._my_dependency.get_queue_size()),
            "processing_rate": self._my_dependency.get_rate()
        }
    
    # Service-specific methods
    async def process_data(self, data: MyDataModel) -> MyResultModel:
        """Process data using the service."""
        self._track_request()
        try:
            result = await self._my_dependency.process(data)
            return result
        except Exception as e:
            self._track_error(e)
            raise
```

## Conclusion

This base service design provides maximum clarity and simplicity while maintaining the flexibility needed for CIRIS's diverse service ecosystem. It enforces consistent patterns, provides comprehensive observability, and makes it easy to add new services that follow established conventions.