# Telemetry Module

The telemetry module provides comprehensive observability and resource monitoring for the CIRIS agent while maintaining strict security and privacy standards. It offers real-time metrics collection, resource monitoring, security filtering, and agent self-awareness capabilities through a sophisticated collector framework.

## Core Principles

### Security-First Design
- **No PII or Conversation Content**: Metrics never contain personally identifiable information or conversation details
- **Secure by Default**: All external endpoints require authentication and TLS
- **Security Filtering**: All telemetry data passes through security filters before collection
- **Fail Secure**: Telemetry failures don't affect agent operation

### Agent Self-Awareness
- **Full Introspection**: Agents have complete visibility into their own metrics via SystemSnapshot
- **Resource Management**: Real-time resource usage monitoring and limit enforcement
- **Performance Insights**: Detailed performance metrics for optimization
- **Health Monitoring**: Continuous health checks and status reporting

## Architecture Overview

### Core Components

```
Telemetry Module
├── TelemetryService (core.py)          # Central metrics collection service
├── ResourceMonitor (resource_monitor.py) # System resource monitoring
├── SecurityFilter (security.py)         # Security and privacy filtering
├── CollectorManager (collectors.py)     # Multi-tier collector framework
└── ResourceSignalBus                    # Resource event coordination
```

### Integration Pattern

```python
from ciris_engine.telemetry import (
    TelemetryService,
    ResourceMonitor, 
    SecurityFilter,
    CollectorManager
)

# Initialize telemetry stack
security_filter = SecurityFilter()
telemetry_service = TelemetryService(
    buffer_size=1000,
    security_filter=security_filter
)
resource_monitor = ResourceMonitor()
collector_manager = CollectorManager(telemetry_service)

# Start services
await telemetry_service.start()
await resource_monitor.start()
await collector_manager.start()
```

## TelemetryService (`core.py`)

The central telemetry service provides secure metrics collection with automatic filtering and agent introspection capabilities.

### Core Features

- **Secure Metric Collection**: All metrics filtered through security layer
- **Time-Series Storage**: Efficient in-memory time-series data with configurable retention
- **SystemSnapshot Integration**: Real-time agent introspection via system snapshots
- **Automatic Pruning**: Time-based data retention with configurable limits

### Basic Usage

```python
from ciris_engine.telemetry import TelemetryService, SecurityFilter
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot

# Initialize service
telemetry = TelemetryService(
    buffer_size=1000,  # Keep last 1000 data points per metric
    security_filter=SecurityFilter()
)

await telemetry.start()

# Record metrics (automatically filtered for security)
await telemetry.record_metric("message_processed", 1.0)
await telemetry.record_metric("response_time_ms", 245.7)
await telemetry.record_metric("llm_tokens_used", 1024)
await telemetry.record_metric("error", 1.0)  # Error occurred

# Get agent introspection via SystemSnapshot
snapshot = SystemSnapshot()
await telemetry.update_system_snapshot(snapshot)

print(f"Messages processed (24h): {snapshot.telemetry.messages_processed_24h}")
print(f"Errors (24h): {snapshot.telemetry.errors_24h}")
print(f"Uptime: {snapshot.telemetry.uptime_hours} hours")
```

### Metric Categories

#### Core Performance Metrics
```python
# Message processing metrics
await telemetry.record_metric("message_processed", 1.0)
await telemetry.record_metric("message_filtered", 1.0) 
await telemetry.record_metric("message_priority_high", 1.0)

# Response time metrics
await telemetry.record_metric("response_time_ms", response_time)
await telemetry.record_metric("llm_response_time_ms", llm_time)
await telemetry.record_metric("memory_operation_time_ms", memory_time)

# Resource usage metrics
await telemetry.record_metric("llm_tokens_used", token_count)
await telemetry.record_metric("memory_operations", 1.0)
await telemetry.record_metric("tool_executions", 1.0)
```

#### Error and Health Metrics
```python
# Error tracking
await telemetry.record_metric("error", 1.0)
await telemetry.record_metric("llm_error", 1.0)
await telemetry.record_metric("memory_error", 1.0)
await telemetry.record_metric("network_error", 1.0)

# Health indicators
await telemetry.record_metric("health_check_success", 1.0)
await telemetry.record_metric("service_restart", 1.0)
await telemetry.record_metric("circuit_breaker_open", 1.0)
```

#### Thought and Processing Metrics
```python
# Cognitive processing
await telemetry.record_metric("thought", 1.0)
await telemetry.record_metric("thought_dma_evaluation", 1.0)
await telemetry.record_metric("guardrail_triggered", 1.0)
await telemetry.record_metric("deferral_to_wa", 1.0)

# Learning and adaptation
await telemetry.record_metric("filter_adaptation", 1.0)
await telemetry.record_metric("config_update", 1.0)
await telemetry.record_metric("trust_score_update", 1.0)
```

### SystemSnapshot Integration

```python
class AgentIntrospection:
    def __init__(self, telemetry_service: TelemetryService):
        self.telemetry = telemetry_service
    
    async def get_current_status(self) -> Dict[str, Any]:
        """Get complete agent status with telemetry data"""
        snapshot = SystemSnapshot()
        await self.telemetry.update_system_snapshot(snapshot)
        
        return {
            "performance": {
                "messages_processed_24h": snapshot.telemetry.messages_processed_24h,
                "thoughts_generated_24h": snapshot.telemetry.thoughts_24h,
                "uptime_hours": snapshot.telemetry.uptime_hours,
                "errors_24h": snapshot.telemetry.errors_24h
            },
            "health": {
                "error_rate": snapshot.telemetry.errors_24h / max(snapshot.telemetry.messages_processed_24h, 1),
                "operational_status": "healthy" if snapshot.telemetry.errors_24h < 10 else "degraded"
            },
            "timestamp": snapshot.telemetry.epoch_seconds
        }
    
    async def check_performance_thresholds(self) -> Dict[str, bool]:
        """Check if agent performance is within acceptable thresholds"""
        status = await self.get_current_status()
        performance = status["performance"]
        
        return {
            "error_rate_acceptable": status["health"]["error_rate"] < 0.05,  # < 5% error rate
            "processing_volume_healthy": performance["messages_processed_24h"] > 0,
            "uptime_stable": performance["uptime_hours"] > 1.0,  # Been running for at least 1 hour
            "thought_generation_active": performance["thoughts_generated_24h"] > 0
        }
```

## ResourceMonitor (`resource_monitor.py`)

Provides comprehensive system resource monitoring with optional psutil integration, resource limit enforcement, and proactive resource management.

### Core Features

- **System Resource Monitoring**: CPU, memory, disk, and network monitoring
- **Resource Limit Enforcement**: Configurable limits with automatic actions
- **Signal Bus Integration**: Event-driven resource management
- **Optional psutil Integration**: Enhanced monitoring when psutil is available
- **Resource Budget Management**: Predictive resource allocation

### Resource Monitoring Setup

```python
from ciris_engine.telemetry import ResourceMonitor, ResourceSignalBus
from ciris_engine.schemas.resource_schemas_v1 import ResourceBudget, ResourceLimit

# Initialize signal bus for resource events
signal_bus = ResourceSignalBus()

# Register resource event handlers
async def handle_throttle(signal: str, resource: str):
    logger.warning(f"Resource throttling activated for {resource}")
    # Implement throttling logic

async def handle_resource_limit(signal: str, resource: str):
    logger.critical(f"Resource limit exceeded for {resource}")
    # Implement emergency resource management

signal_bus.register("throttle", handle_throttle)
signal_bus.register("defer", handle_resource_limit)
signal_bus.register("shutdown", handle_resource_limit)

# Initialize resource monitor
resource_monitor = ResourceMonitor(
    signal_bus=signal_bus,
    monitoring_interval=30,  # Check every 30 seconds
    enable_psutil=True  # Use psutil if available
)

# Configure resource limits
resource_budget = ResourceBudget(
    cpu_limit=ResourceLimit(warning_threshold=70.0, critical_threshold=90.0),
    memory_limit=ResourceLimit(warning_threshold=80.0, critical_threshold=95.0),
    disk_limit=ResourceLimit(warning_threshold=85.0, critical_threshold=95.0)
)

await resource_monitor.start()
await resource_monitor.set_resource_budget(resource_budget)
```

### Resource Monitoring Usage

```python
class ResourceAwareAgent:
    def __init__(self, resource_monitor: ResourceMonitor):
        self.resource_monitor = resource_monitor
    
    async def check_resource_availability(self) -> bool:
        """Check if resources are available for processing"""
        snapshot = await self.resource_monitor.get_current_snapshot()
        
        # Check if any resources are at critical levels
        if snapshot.cpu_usage > 90.0:
            logger.warning("CPU usage critical, deferring processing")
            return False
        
        if snapshot.memory_usage > 95.0:
            logger.warning("Memory usage critical, deferring processing")
            return False
        
        if snapshot.disk_usage > 95.0:
            logger.warning("Disk usage critical, deferring processing")
            return False
        
        return True
    
    async def process_with_resource_awareness(self, task):
        """Process task with resource monitoring"""
        if not await self.check_resource_availability():
            # Queue task for later when resources improve
            await self.queue_for_later(task)
            return
        
        # Monitor resources during processing
        start_snapshot = await self.resource_monitor.get_current_snapshot()
        
        try:
            result = await self.process_task(task)
            
            # Record resource usage metrics
            end_snapshot = await self.resource_monitor.get_current_snapshot()
            await self.record_resource_usage(start_snapshot, end_snapshot)
            
            return result
            
        except Exception as e:
            logger.error(f"Task processing failed: {e}")
            # Check if failure was resource-related
            current_snapshot = await self.resource_monitor.get_current_snapshot()
            if self.is_resource_exhausted(current_snapshot):
                await self.handle_resource_exhaustion()
            raise
```

## SecurityFilter (`security.py`)

Provides comprehensive security filtering for all telemetry data to prevent information leakage and maintain privacy standards.

### Security Features

- **PII Detection and Removal**: Automatic detection and filtering of personally identifiable information
- **Content Sanitization**: Removal of sensitive content from metric names and values
- **Allowlist/Blocklist Management**: Configurable filtering rules
- **Pattern-Based Filtering**: Regex-based detection of sensitive patterns
- **Value Range Validation**: Ensures metric values are within acceptable ranges

### Security Filter Usage

```python
from ciris_engine.telemetry import SecurityFilter

# Initialize security filter with custom rules
security_filter = SecurityFilter(
    enable_pii_detection=True,
    enable_content_filtering=True,
    max_metric_name_length=100,
    allowed_metric_prefixes=[
        "performance.",
        "health.", 
        "resource.",
        "error.",
        "processing."
    ],
    blocked_patterns=[
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN pattern
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email pattern
        r"\b(?:\d{4}[- ]?){3}\d{4}\b",  # Credit card pattern
    ]
)

# Filter metrics before recording
filtered_result = security_filter.sanitize("user_email_processed", "user@example.com")
if filtered_result is not None:
    metric_name, metric_value = filtered_result
    await telemetry.record_metric(metric_name, metric_value)
else:
    logger.debug("Metric filtered out by security filter")
```

## Collector Framework (`collectors.py`)

Provides a sophisticated multi-tier collector framework for efficient telemetry data collection with different performance characteristics.

### Collector Hierarchy

```
CollectorManager
├── InstantCollector     # Immediate collection (0ms delay)
├── FastCollector        # Fast collection (100ms intervals)
├── NormalCollector      # Normal collection (1s intervals)
├── SlowCollector        # Slow collection (10s intervals)
└── AggregateCollector   # Aggregated collection (60s intervals)
```

### Collector Usage

```python
from ciris_engine.telemetry import (
    CollectorManager,
    InstantCollector,
    FastCollector,
    NormalCollector,
    MetricData
)

# Initialize collector manager
collector_manager = CollectorManager(telemetry_service)

# Register instant metrics (critical performance indicators)
instant_collector = InstantCollector("performance", telemetry_service)
instant_collector.register_metric("message_processed")
instant_collector.register_metric("error")
instant_collector.register_metric("critical_alert")

# Register fast metrics (high-frequency monitoring)
fast_collector = FastCollector("system", telemetry_service, interval=0.1)
fast_collector.register_metric("cpu_usage")
fast_collector.register_metric("memory_usage")
fast_collector.register_metric("active_connections")

# Register normal metrics (standard monitoring)
normal_collector = NormalCollector("operations", telemetry_service, interval=1.0)
normal_collector.register_metric("llm_requests")
normal_collector.register_metric("memory_operations")
normal_collector.register_metric("tool_executions")

# Add collectors to manager
collector_manager.add_collector(instant_collector)
collector_manager.add_collector(fast_collector)
collector_manager.add_collector(normal_collector)

# Start collection
await collector_manager.start()
```

## Integration Patterns

### Service Integration

```python
class TelemetryAwareService(Service):
    """Base class for services with telemetry integration"""
    
    def __init__(self, telemetry_service: TelemetryService):
        super().__init__()
        self.telemetry = telemetry_service
        self.service_name = self.__class__.__name__
    
    async def record_operation(self, operation: str, duration: float = None, success: bool = True):
        """Record service operation metrics"""
        metric_name = f"{self.service_name.lower()}.{operation}"
        
        # Record operation count
        await self.telemetry.record_metric(f"{metric_name}.count", 1.0)
        
        # Record duration if provided
        if duration is not None:
            await self.telemetry.record_metric(f"{metric_name}.duration_ms", duration)
        
        # Record success/failure
        if success:
            await self.telemetry.record_metric(f"{metric_name}.success", 1.0)
        else:
            await self.telemetry.record_metric(f"{metric_name}.error", 1.0)
    
    async def execute_with_telemetry(self, operation_name: str, operation_func, *args, **kwargs):
        """Execute operation with automatic telemetry recording"""
        start_time = datetime.utcnow()
        
        try:
            result = await operation_func(*args, **kwargs)
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.record_operation(operation_name, duration, success=True)
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.record_operation(operation_name, duration, success=False)
            
            # Record specific error types
            error_type = type(e).__name__
            await self.telemetry.record_metric(f"{self.service_name.lower()}.error.{error_type.lower()}", 1.0)
            
            raise
```

## Performance Optimization

### Efficient Data Collection

```python
class OptimizedTelemetryService(TelemetryService):
    """Optimized telemetry service with batching and compression"""
    
    def __init__(self, buffer_size: int = 1000, batch_size: int = 100):
        super().__init__(buffer_size)
        self.batch_size = batch_size
        self.metric_batch = []
        self.batch_lock = asyncio.Lock()
    
    async def record_metric(self, metric_name: str, value: float = 1.0) -> None:
        """Record metric with batching for efficiency"""
        async with self.batch_lock:
            self.metric_batch.append((metric_name, value, datetime.utcnow()))
            
            if len(self.metric_batch) >= self.batch_size:
                await self.flush_batch()
    
    async def flush_batch(self):
        """Flush batched metrics to storage"""
        if not self.metric_batch:
            return
        
        batch = self.metric_batch.copy()
        self.metric_batch.clear()
        
        # Process batch efficiently
        for metric_name, value, timestamp in batch:
            sanitized = self._filter.sanitize(metric_name, value)
            if sanitized is not None:
                name, val = sanitized
                self._history[name].append((timestamp, float(val)))
```

## Troubleshooting

### Common Issues and Solutions

#### Telemetry Service Not Recording Metrics

```python
# Debug telemetry recording issues
async def debug_telemetry_issues(telemetry_service: TelemetryService):
    """Debug common telemetry recording problems"""
    
    # Test basic metric recording
    test_metric = "debug_test_metric"
    await telemetry_service.record_metric(test_metric, 1.0)
    
    # Check if metric was recorded
    if test_metric in telemetry_service._history:
        print("✓ Basic metric recording working")
    else:
        print("✗ Basic metric recording failed")
        print("Check security filter configuration")
    
    # Test security filter
    security_filter = telemetry_service._filter
    filtered_result = security_filter.sanitize("test_metric", 1.0)
    
    if filtered_result is not None:
        print("✓ Security filter allowing test metrics")
    else:
        print("✗ Security filter blocking all metrics")
        print("Review security filter rules")
    
    # Check service status
    if hasattr(telemetry_service, '_running') and telemetry_service._running:
        print("✓ Telemetry service is running")
    else:
        print("✗ Telemetry service not started")
        print("Call await telemetry_service.start()")
```

#### Resource Monitor Integration Issues

```python
# Diagnose resource monitoring problems
async def diagnose_resource_monitor(resource_monitor: ResourceMonitor):
    """Diagnose resource monitoring issues"""
    
    # Check psutil availability
    try:
        import psutil
        print("✓ psutil available for enhanced monitoring")
        print(f"  CPU count: {psutil.cpu_count()}")
        print(f"  Memory: {psutil.virtual_memory().total / (1024**3):.1f} GB")
    except ImportError:
        print("⚠ psutil not available, using basic monitoring")
    
    # Test resource snapshot
    try:
        snapshot = await resource_monitor.get_current_snapshot()
        print("✓ Resource snapshot working")
        print(f"  CPU: {snapshot.cpu_usage:.1f}%")
        print(f"  Memory: {snapshot.memory_usage:.1f}%")
        print(f"  Disk: {snapshot.disk_usage:.1f}%")
    except Exception as e:
        print(f"✗ Resource snapshot failed: {e}")
        print("Check resource monitor configuration and permissions")
```

---

The telemetry module provides a comprehensive, secure, and efficient observability framework that enables CIRIS agents to maintain full self-awareness while protecting sensitive information and maintaining optimal performance through sophisticated resource monitoring and multi-tier data collection.