"""
Minimal telemetry for self-awareness on constrained devices.
All metrics designed to fit in <4KB total.
"""
from pydantic import BaseModel, Field
from typing import Dict, List
from .versioning import SchemaVersion

class ResourceMetrics(BaseModel):
    """Track resource usage for self-limitation"""
    memory_mb: int = 0  # Current memory usage
    cpu_percent: int = 0  # 0-100
    tokens_used_1h: int = 0  # Rolling hour window
    estimated_cost_cents: int = 0  # In cents to avoid float

class CompactTelemetry(BaseModel):
    """Fits in one memory page (4KB)"""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Core operation (16 bytes)
    thoughts_active: int = 0
    thoughts_24h: int = 0  # Rolling 24h count
    avg_latency_ms: int = 0
    uptime_hours: int = 0
    
    # Resources (16 bytes)  
    resources: ResourceMetrics = Field(default_factory=ResourceMetrics)
    
    # Safety (24 bytes)
    guardrail_hits: int = 0
    deferrals_24h: int = 0
    errors_24h: int = 0
    drift_score: int = Field(default=0, ge=0, le=100)  # 0=aligned, 100=drifted
    
    # Community impact (16 bytes)
    messages_processed_24h: int = 0
    helpful_actions_24h: int = 0
    community_health_delta: int = 0  # -100 to +100
    
    # Wisdom seeking (8 bytes)
    wa_available: bool = True
    isolation_hours: int = 0  # Hours without WA contact
    universal_guidance_count: int = 0  # Times sought universal wisdom
    
    epoch_seconds: int = 0  # Last update