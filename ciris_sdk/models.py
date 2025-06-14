from __future__ import annotations

from typing import Optional, List, Any, Dict
from pydantic import BaseModel

class Message(BaseModel):
    id: str
    content: str
    author_id: str
    author_name: str
    channel_id: str
    timestamp: Optional[str] = None

class MemoryEntry(BaseModel):
    key: str
    value: Any

class MemoryScope(BaseModel):
    name: str
    entries: Optional[List[MemoryEntry]] = None

# Runtime Control Models
class ProcessorControlResponse(BaseModel):
    success: bool
    action: str
    timestamp: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class AdapterInfo(BaseModel):
    adapter_id: str
    adapter_type: str
    is_running: bool
    health_status: str
    services_count: int
    loaded_at: str
    config_params: Dict[str, Any]

class AdapterLoadRequest(BaseModel):
    adapter_type: str
    adapter_id: Optional[str] = None
    config: Dict[str, Any] = {}
    auto_start: bool = True

class AdapterOperationResponse(BaseModel):
    success: bool
    adapter_id: str
    adapter_type: str
    services_registered: Optional[int] = None
    services_unregistered: Optional[int] = None
    loaded_at: Optional[str] = None
    was_running: Optional[bool] = None
    error: Optional[str] = None

class RuntimeStatus(BaseModel):
    processor_status: str
    active_adapters: List[str]
    loaded_adapters: List[str]
    current_profile: str
    config_scope: str
    uptime_seconds: float
    last_config_change: Optional[str] = None
    health_status: str = "healthy"

class ConfigOperationResponse(BaseModel):
    success: bool
    operation: str
    timestamp: str
    path: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    scope: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

# System Telemetry Models
class SystemHealth(BaseModel):
    overall_health: str
    adapters_healthy: int
    services_healthy: int
    processor_status: str
    memory_usage_mb: float
    uptime_seconds: float

class TelemetrySnapshot(BaseModel):
    timestamp: str
    schema_version: str
    runtime_uptime_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float
    overall_health: str
    adapters: List[AdapterInfo]
    processor_state: Dict[str, Any]
    configuration: Dict[str, Any]

class ServiceInfo(BaseModel):
    name: str
    service_type: str
    handler: Optional[str] = None
    priority: str
    capabilities: List[str]
    status: str
    circuit_breaker_state: str
    metadata: Dict[str, Any]

class ProcessorState(BaseModel):
    is_running: bool
    current_round: int
    thoughts_pending: int
    thoughts_processing: int
    thoughts_completed_24h: int
    last_activity: Optional[str] = None
    processor_mode: str
    idle_rounds: int

class MetricRecord(BaseModel):
    metric_name: str
    value: float
    tags: Dict[str, str] = {}
    timestamp: str

class DeferralInfo(BaseModel):
    deferral_id: str
    thought_id: str
    reason: str
    context: Dict[str, Any]
    status: str
    created_at: str
    resolved_at: Optional[str] = None
