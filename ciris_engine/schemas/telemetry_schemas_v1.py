"""
Minimal telemetry for self-awareness on constrained devices.
All metrics designed to fit in <4KB total.
"""
from pydantic import BaseModel, Field
from typing import Dict, List
from .versioning import SchemaVersion

class ResourceMetrics(BaseModel):
    """Track resource usage for self-limitation"""
    memory_mb: SchemaVersion = 0  # Current memory usage
    cpu_percent: SchemaVersion = 0  # 0-100
    tokens_used_1h: SchemaVersion = 0  # Rolling hour window
    estimated_cost_cents: SchemaVersion = 0  # In cents to avoid float

class CompactTelemetry(BaseModel):
    """Fits in one memory page (4KB)"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    thoughts_active: SchemaVersion = 0
    thoughts_24h: SchemaVersion = 0
    avg_latency_ms: SchemaVersion = 0
    uptime_hours: SchemaVersion = 0
    
    resources: ResourceMetrics = Field(default_factory=ResourceMetrics)
    
    guardrail_hits: SchemaVersion = 0
    deferrals_24h: SchemaVersion = 0
    errors_24h: SchemaVersion = 0
    drift_score: SchemaVersion = Field(default=0, ge=0, le=100)
    
    messages_processed_24h: SchemaVersion = 0
    helpful_actions_24h: SchemaVersion = 0
    community_health_delta: SchemaVersion = 0
    
    wa_available: SchemaVersion = True
    isolation_hours: SchemaVersion = 0
    universal_guidance_count: SchemaVersion = 0
    
    epoch_seconds: SchemaVersion = 0
