"""
Runtime Control Interface Protocol

Defines the interface for runtime system control including processor management,
adapter lifecycle management, and configuration operations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from ciris_engine.schemas.config_schemas_v1 import AgentProfile


class AdapterLoadRequest(BaseModel):
    """Request to load a new adapter"""
    adapter_type: str  # 'discord', 'cli', 'api', etc.
    adapter_config: Dict[str, Any]  # Adapter-specific configuration
    profile: Optional[AgentProfile] = None  # Optional agent profile for the adapter
    auto_start: bool = True  # Whether to start the adapter immediately


class AdapterLoadResult(BaseModel):
    """Result of adapter load operation"""
    success: bool
    adapter_id: str
    adapter_type: str
    status: str  # 'loaded', 'started', 'error'
    error_message: Optional[str] = None
    services_registered: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class AdapterUnloadResult(BaseModel):
    """Result of adapter unload operation"""
    success: bool
    adapter_id: str
    status: str  # 'unloaded', 'stopped', 'error'
    error_message: Optional[str] = None
    services_unregistered: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class ProcessorControlResult(BaseModel):
    """Result of processor control operation"""
    success: bool
    operation: str  # 'start', 'stop', 'pause', 'resume', 'single_step'
    status: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class RuntimeState(BaseModel):
    """Current state of the runtime system"""
    is_running: bool
    processor_status: str  # 'running', 'paused', 'stopped', 'error'
    loaded_adapters: List[str] = Field(default_factory=list)
    active_adapters: List[str] = Field(default_factory=list)
    total_services: int = 0
    uptime_seconds: float = 0.0
    last_activity: Optional[datetime] = None


class RuntimeControlInterface(ABC):
    """Protocol for runtime system control and management"""
    
    # Processor Control Methods
    @abstractmethod
    async def start_processing(self, num_rounds: Optional[int] = None) -> ProcessorControlResult:
        """Start the processor with optional round limit"""
        ...
    
    @abstractmethod
    async def stop_processing(self) -> ProcessorControlResult:
        """Stop the processor gracefully"""
        ...
    
    @abstractmethod
    async def pause_processing(self) -> ProcessorControlResult:
        """Pause the processor temporarily"""
        ...
    
    @abstractmethod
    async def resume_processing(self) -> ProcessorControlResult:
        """Resume a paused processor"""
        ...
    
    @abstractmethod
    async def single_step(self) -> ProcessorControlResult:
        """Execute a single processing step"""
        ...
    
    # Adapter Management Methods
    @abstractmethod
    async def load_adapter(self, request: AdapterLoadRequest) -> AdapterLoadResult:
        """Load and optionally start a new adapter"""
        ...
    
    @abstractmethod
    async def unload_adapter(self, adapter_id: str) -> AdapterUnloadResult:
        """Stop and unload an adapter"""
        ...
    
    @abstractmethod
    async def start_adapter(self, adapter_id: str) -> AdapterLoadResult:
        """Start a loaded but stopped adapter"""
        ...
    
    @abstractmethod
    async def stop_adapter(self, adapter_id: str) -> AdapterUnloadResult:
        """Stop a running adapter without unloading it"""
        ...
    
    @abstractmethod
    async def list_adapters(self) -> List[Dict[str, Any]]:
        """List all loaded adapters and their status"""
        ...
    
    # Configuration Management Methods
    @abstractmethod
    async def reload_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Reload system configuration"""
        ...
    
    @abstractmethod
    async def update_profile(self, profile_name: str, profile: AgentProfile) -> Dict[str, Any]:
        """Update or add an agent profile"""
        ...
    
    @abstractmethod
    async def switch_profile(self, profile_name: str) -> Dict[str, Any]:
        """Switch to a different agent profile"""
        ...
    
    # System State Methods
    @abstractmethod
    async def get_runtime_state(self) -> RuntimeState:
        """Get current runtime state"""
        ...
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive system health check"""
        ...
    
    @abstractmethod
    async def restart_runtime(self, preserve_state: bool = True) -> Dict[str, Any]:
        """Restart the runtime system"""
        ...
