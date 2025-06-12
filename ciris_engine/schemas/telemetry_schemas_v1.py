"""
Minimal telemetry for self-awareness on constrained devices.
All metrics designed to fit in <4KB total.
"""
from pydantic import BaseModel, Field
from .versioning import SchemaVersion

class ResourceMetrics(BaseModel):
    """Track resource usage for self-limitation"""
    memory_mb: int = 0  # Current memory usage
    cpu_percent: float = 0  # 0-100
    tokens_used_1h: int = 0  # Rolling hour window
    estimated_cost_cents: int = 0  # In cents to avoid float

class CompactTelemetry(BaseModel):
    """Fits in one memory page (4KB)"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    thoughts_active: int = 0
    thoughts_24h: int = 0
    avg_latency_ms: int = 0
    uptime_hours: float = 0
    
    resources: ResourceMetrics = Field(default_factory=ResourceMetrics)
    
    guardrail_hits: int = 0
    deferrals_24h: int = 0
    errors_24h: int = 0
    drift_score: int = Field(default=0, ge=0, le=100)
    
    messages_processed_24h: int = 0
    helpful_actions_24h: int = 0
    gratitude_expressed_24h: int = 0
    gratitude_received_24h: int = 0
    community_health_delta: int = 0
    
    wa_available: bool = True
    isolation_hours: int = 0
    universal_guidance_count: int = 0
    
    epoch_seconds: int = 0
