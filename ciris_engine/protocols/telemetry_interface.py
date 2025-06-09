"""
Telemetry Interface Protocol

Defines the interface for comprehensive system telemetry including adapters,
services, configuration, processor state, and runtime metrics.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from ciris_engine.schemas.telemetry_schemas_v1 import CompactTelemetry
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.registries.base import Priority


class AdapterInfo(BaseModel):
    """Information about a registered platform adapter"""
    name: str
    type: str
    status: str  # 'active', 'inactive', 'error'
    capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    start_time: Optional[datetime] = None
    last_activity: Optional[datetime] = None


class ServiceInfo(BaseModel):
    """Information about a registered service"""
    name: str
    service_type: str
    handler: Optional[str] = None  # None for global services
    priority: str
    capabilities: List[str] = Field(default_factory=list)
    status: str  # 'healthy', 'degraded', 'failed', 'unknown'
    circuit_breaker_state: str  # 'closed', 'open', 'half_open'
    metadata: Dict[str, Any] = Field(default_factory=dict)
    instance_id: str


class ProcessorState(BaseModel):
    """Current state of the agent processor"""
    is_running: bool = False
    current_round: int = 0
    thoughts_pending: int = 0
    thoughts_processing: int = 0
    thoughts_completed_24h: int = 0
    last_activity: Optional[datetime] = None
    processor_mode: str = "unknown"  # 'work', 'dream', 'wakeup', 'idle'
    idle_rounds: int = 0


class ConfigurationSnapshot(BaseModel):
    """Snapshot of current system configuration"""
    profile_name: str
    startup_channel_id: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None
    database_path: Optional[str] = None
    telemetry_enabled: bool = True
    debug_mode: bool = False
    adapter_modes: List[str] = Field(default_factory=list)
    
    # DMA Configuration
    ethical_dma: Optional[str] = None
    csdma: Optional[str] = None
    dsdma: Optional[str] = None
    action_selection_dma: Optional[str] = None
    
    # Guardrails Configuration
    active_guardrails: List[str] = Field(default_factory=list)
    guardrail_settings: Dict[str, Any] = Field(default_factory=dict)


class TelemetrySnapshot(BaseModel):
    """Complete system telemetry snapshot"""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = "v1.0"
    
    # Basic metrics
    basic_telemetry: CompactTelemetry
    
    # System components
    adapters: List[AdapterInfo] = Field(default_factory=list)
    services: List[ServiceInfo] = Field(default_factory=list)
    processor_state: ProcessorState
    configuration: ConfigurationSnapshot
    
    # Runtime information
    runtime_uptime_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Health indicators
    overall_health: str = "unknown"  # 'healthy', 'degraded', 'critical'
    health_details: Dict[str, str] = Field(default_factory=dict)


class TelemetryInterface(ABC):
    """Protocol for comprehensive system telemetry collection and reporting"""
    
    @abstractmethod
    async def get_telemetry_snapshot(self) -> TelemetrySnapshot:
        """Get a complete snapshot of current system telemetry"""
        ...
    
    @abstractmethod
    async def get_adapters_info(self) -> List[AdapterInfo]:
        """Get information about all registered adapters"""
        ...
    
    @abstractmethod
    async def get_services_info(self) -> List[ServiceInfo]:
        """Get information about all registered services"""
        ...
    
    @abstractmethod
    async def get_processor_state(self) -> ProcessorState:
        """Get current processor state information"""
        ...
    
    @abstractmethod
    async def get_configuration_snapshot(self) -> ConfigurationSnapshot:
        """Get current system configuration"""
        ...
    
    @abstractmethod
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        ...
    
    @abstractmethod
    async def record_metric(self, metric_name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None) -> None:
        """Record a custom metric with optional tags"""
        ...
    
    @abstractmethod
    async def get_metrics_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical data for a specific metric"""
        ...


class ProcessorControlInterface(ABC):
    """Protocol for controlling processor execution"""
    
    @abstractmethod
    async def single_step(self) -> Dict[str, Any]:
        """Execute a single processing step and return results"""
        ...
    
    @abstractmethod
    async def pause_processing(self) -> bool:
        """Pause the processor"""
        ...
    
    @abstractmethod
    async def resume_processing(self) -> bool:
        """Resume the processor"""
        ...
    
    @abstractmethod
    async def get_processing_queue_status(self) -> Dict[str, Any]:
        """Get current processing queue status"""
        ...