# CIRIS Agent Telemetry System

## Overview

The CIRIS Agent includes a comprehensive telemetry system that provides real-time observability into agent operations while maintaining strict security and privacy controls. The system collects performance metrics, operational statistics, and health indicators to enable monitoring, debugging, and optimization.

## Architecture

The telemetry system implements the "Graph Memory as Identity Architecture" patent, where telemetry IS memory stored in the agent's identity graph.

### 1. GraphTelemetryService (`ciris_engine/logic/services/graph/telemetry_service.py`)
- **Graph-Based Storage**: All metrics stored as TSDBGraphNodes in memory graph
- **Time-Travel Queries**: Agent can query its historical performance
- **Self-Introspection**: Metrics accessible through RECALL operations
- **Identity Integration**: Telemetry is part of the agent's identity, not separate

### 2. Adapter Telemetry Pattern
- **No Direct Collection**: Adapters don't have telemetry collectors
- **Memory Bus Emission**: Adapters emit telemetry as memory operations
- **Dynamic Adapter Support**: Works with adapters added/removed at runtime
- **Multi-Adapter Awareness**: Tracks metrics per adapter instance

### 3. SystemSnapshot Integration
- **Real-Time View**: Current metrics available in agent context
- **No External Dependencies**: Agent accesses its own metrics through memory
- **Continuous Feedback**: Enables self-configuration and adaptation
- **Resource Awareness**: Agent understands its own resource usage

### 4. Memory Bus Flow
```python
# Adapters emit telemetry as memories
await bus_manager.memory.memorize(
    node=GraphNode(
        id=f"telemetry_{timestamp}_{metric_name}",
        type=NodeType.TELEMETRY,
        scope=GraphScope.LOCAL,
        attributes={
            "metric_name": "messages_processed",
            "value": 1,
            "adapter_id": self.adapter_id,
            "timestamp": now
        }
    ),
    handler_name="adapter.discord",
    metadata={"source": "telemetry"}
)
```

## Why This Architecture?

### Telemetry as Memory, Not Metrics
Traditional telemetry systems treat metrics as separate from the application. In CIRIS:
- **Telemetry IS Memory**: Metrics are TSDBGraphNodes in the agent's identity graph
- **Self-Introspection**: Agent can RECALL its own performance history
- **Unified Identity**: Performance data is part of "who the agent is"
- **Autonomous Adaptation**: Agent uses its history to self-configure

### Benefits Over Traditional Telemetry
1. **No External Dependencies**: Agent doesn't need external metric servers
2. **Natural Time-Travel**: Graph queries provide historical analysis
3. **Identity Coherence**: Performance patterns are part of identity
4. **Dynamic Adapter Support**: New adapters automatically integrate
5. **Self-Configuration**: Agent learns from its own metrics

## Key Features

### 🔒 **Security-First Design**
- All metrics filtered for PII before collection
- Error messages sanitized to remove sensitive data
- Rate limiting prevents information leakage
- Configurable sensitivity levels

### 📊 **Multi-Tier Collection**

#### Instant Collector (50ms)
- Circuit breaker states
- Critical error counts
- Emergency shutdown triggers
- Security alerts

#### Fast Collector (250ms)
- Active thoughts count
- Handler selection metrics
- Processing queue sizes
- LLM API response times

#### Normal Collector (1s)
- Resource usage (memory, CPU)
- Guardrail activations
- Service health checks
- Database connection status

#### Slow Collector (5s)
- Memory operations (recall, memorize)
- DMA execution metrics (with sanitization)
- Complex aggregations
- Historical trend data

#### Aggregate Collector (30s)
- Community metrics rollups
- Long-term performance trends
- System health summaries
- Audit log statistics

### 🎯 **Agent Introspection**
The telemetry system integrates with the agent's context through SystemSnapshot:

```python
class CompactTelemetry(BaseModel):
    """Telemetry data for agent introspection"""
    active_thoughts: int = 0
    recent_errors: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    llm_tokens_used: int = 0
    guardrails_active: int = 0
    last_action_latency_ms: float = 0.0
    circuit_breakers_open: int = 0
    performance_score: float = 1.0
```

## Integration Points

### SystemSnapshot Integration
The agent accesses its telemetry through memory recall and SystemSnapshot:

```python
# Agent recalls its own metrics
metrics_query = MemoryQuery(
    scope=GraphScope.LOCAL,
    filters={"type": "TELEMETRY", "time_range": "1h"}
)
recent_metrics = await memory_service.recall(metrics_query)

# SystemSnapshot provides real-time view
snapshot.telemetry.active_thoughts = active_count
snapshot.telemetry.tokens_consumed_total = total_tokens
```

### Component Instrumentation

#### Adapters
```python
# Adapter lifecycle and message metrics
await self.bus_manager.memory.memorize(
    node=create_telemetry_node("adapter_started", {"adapter_id": self.adapter_id}),
    handler_name=f"adapter.{self.adapter_type}"
)

# Message processing
await self.bus_manager.memory.memorize(
    node=create_telemetry_node("message_received", {
        "channel": channel_id,
        "latency_ms": processing_time
    }),
    handler_name=f"adapter.{self.adapter_type}"
)
```

#### ThoughtProcessor
```python
# Thought lifecycle stored as memories
await self.bus_manager.memory.memorize(
    node=create_telemetry_node("thought_started", {
        "thought_type": thought.thought_type,
        "thought_id": thought.id
    }),
    handler_name="thought_processor"
)
```

#### LLM Service
```python
# Resource usage as memories for self-awareness
await self.bus_manager.memory.memorize(
    node=create_telemetry_node("llm_usage", {
        "tokens": token_count,
        "cost_usd": estimated_cost,
        "co2_grams": estimated_co2,
        "model": model_name
    }),
    handler_name="llm_service"
)
```

### Resource Management
```python
# Resource monitoring and enforcement
monitor = ResourceMonitor(telemetry_service)
await monitor.check_memory_usage()  # Auto-throttle if needed
await monitor.enforce_token_budget()  # LLM rate limiting
```

## Security Model

### PII Detection and Removal
The security filter automatically detects and removes:
- Email addresses
- Phone numbers
- Credit card numbers
- Social security numbers
- API keys and tokens
- IP addresses
- User names and IDs

### Metric Sanitization
```python
# Error messages are cleaned
original_error = "Authentication failed for user john.doe@company.com"
sanitized_error = "Authentication failed for user [EMAIL_REDACTED]"

# Stack traces sanitized
original_trace = "/home/user/secret_project/api_key.py"
sanitized_trace = "/home/[USER]/[PROJECT]/api_key.py"
```

### Rate Limiting
Per-metric-type limits prevent information leakage:
- Error metrics: 10/minute
- Performance metrics: 100/minute
- Resource metrics: 60/minute
- Debug metrics: 20/minute

## Metrics Categories

### Performance Metrics
- **Latency**: Response times for various operations
- **Throughput**: Operations per second
- **Queue Depths**: Pending work backlogs
- **Cache Hit Rates**: Memory and storage efficiency

### Resource Metrics
- **Memory Usage**: Heap, stack, and total memory consumption
- **CPU Usage**: Processing load and thread utilization
- **Disk I/O**: Database and file system operations
- **Network**: API calls and data transfer

### Operational Metrics
- **Error Rates**: Failed operations by category
- **Success Rates**: Successful completions
- **Circuit Breakers**: Protection mechanism activations
- **Guardrails**: Safety mechanism triggers

### Business Metrics
- **Task Completion**: Successful task resolutions
- **User Interactions**: Message processing statistics
- **Feature Usage**: Which capabilities are utilized
- **Quality Scores**: Agent performance assessments

## Configuration

### Telemetry Service Configuration
```python
telemetry_config = {
    "enabled": True,
    "buffer_size": 1000,
    "flush_interval_seconds": 30,
    "security_filter_enabled": True,
    "pii_detection_strict": True,
    "rate_limits": {
        "error_metrics": 10,
        "performance_metrics": 100,
        "resource_metrics": 60
    }
}
```

### Collector Configuration
```python
collector_config = {
    "instant": {"interval_ms": 50, "enabled": True},
    "fast": {"interval_ms": 250, "enabled": True},
    "normal": {"interval_ms": 1000, "enabled": True},
    "slow": {"interval_ms": 5000, "enabled": True},
    "aggregate": {"interval_ms": 30000, "enabled": True}
}
```

### Security Filter Configuration
```python
security_config = {
    "pii_patterns": {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b\d{3}-\d{3}-\d{4}\b',
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b'
    },
    "sanitization_enabled": True,
    "redaction_placeholder": "[REDACTED]"
}
```

## Usage Examples

### Basic Metric Recording
```python
from ciris_engine.telemetry import TelemetryService

telemetry = TelemetryService()

# Record a counter metric
await telemetry.record_metric("user_messages", 1, {"channel": "general"})

# Record a timing metric
await telemetry.record_metric("llm_response_time", 1250.0, {"model": "gpt-4"})

# Record a gauge metric
await telemetry.record_metric("memory_usage_mb", 512.0, {"component": "graph_memory"})
```

### Resource Monitoring
```python
from ciris_engine.telemetry.resource_monitor import ResourceMonitor

monitor = ResourceMonitor(telemetry_service)

# Check if operation should proceed
if await monitor.check_memory_budget():
    # Proceed with memory-intensive operation
    await process_large_dataset()
else:
    # Throttle or defer operation
    await defer_operation()
```

### Custom Collectors
```python
from ciris_engine.telemetry.collectors import BaseCollector

class CustomCollector(BaseCollector):
    def __init__(self, telemetry_service):
        super().__init__(interval_ms=1000)
        self.telemetry = telemetry_service

    async def collect(self):
        # Custom metric collection logic
        custom_value = await get_custom_metric()
        await self.telemetry.record_metric("custom_metric", custom_value)
```

### Retrieving Telemetry Data
```python
# Get current telemetry snapshot
snapshot = await telemetry.get_compact_telemetry()
print(f"Active thoughts: {snapshot.active_thoughts}")
print(f"Memory usage: {snapshot.memory_usage_mb}MB")
print(f"Performance score: {snapshot.performance_score}")

# Get detailed metrics
metrics = await telemetry.get_recent_metrics(minutes=5)
for metric in metrics:
    print(f"{metric.name}: {metric.value} @ {metric.timestamp}")
```

## Monitoring and Alerting

### Built-in Alerts
The system can trigger alerts for:
- Memory usage > 90%
- Error rate > 5%
- Circuit breakers open
- Performance degradation
- Security events

### Integration Points
```python
# Custom alert handlers
async def memory_alert_handler(usage_percent):
    if usage_percent > 90:
        await send_alert(f"High memory usage: {usage_percent}%")

telemetry.register_alert_handler("memory_usage", memory_alert_handler)
```

### External Monitoring
The telemetry system can export data to:
- Prometheus/Grafana
- CloudWatch
- DataDog
- Custom monitoring solutions

## Performance Impact

### Minimal Overhead
- In-memory buffering for fast writes
- Asynchronous processing
- Configurable collection frequencies
- Efficient data structures

### Benchmarks
- Metric recording: < 1ms overhead
- Security filtering: < 5ms per metric
- Buffer flush: < 10ms per 1000 metrics
- Memory overhead: < 50MB baseline

## Testing

### Unit Tests
- `tests/ciris_engine/telemetry/test_telemetry_core.py`
- `tests/ciris_engine/telemetry/test_security_filter.py`
- `tests/ciris_engine/telemetry/test_collectors.py`
- `tests/ciris_engine/telemetry/test_resource_monitor.py`

### Integration Tests
- Component instrumentation validation
- End-to-end metric flow
- Security filter effectiveness
- Performance impact assessment

### Load Tests
- High-frequency metric recording
- Buffer overflow handling
- Concurrent access patterns
- Memory leak detection

## Troubleshooting

### Common Issues

**Missing Metrics**
- Check if telemetry service is enabled
- Verify component instrumentation
- Review rate limiting configuration

**High Memory Usage**
- Adjust buffer sizes
- Increase flush frequency
- Check for metric accumulation

**Performance Impact**
- Review collection frequencies
- Disable non-essential collectors
- Optimize metric recording patterns

### Debug Information
```python
# Enable debug logging
import logging
logging.getLogger('ciris_engine.telemetry').setLevel(logging.DEBUG)

# Get telemetry service status
status = await telemetry.get_service_status()
print(f"Buffer size: {status['buffer_size']}")
print(f"Metrics collected: {status['total_metrics']}")
print(f"Errors: {status['error_count']}")
```

## Future Enhancements

- **Distributed Tracing**: Request tracing across components
- **Machine Learning**: Anomaly detection in metrics
- **Real-time Dashboards**: Live monitoring interfaces
- **Predictive Alerts**: ML-based performance predictions
- **Cost Optimization**: Resource usage optimization recommendations

---

*The telemetry system provides comprehensive observability while maintaining strict security and privacy controls, enabling effective monitoring and optimization of CIRIS Agent operations.*
