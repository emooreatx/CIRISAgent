"""Schemas for runtime control and configuration management."""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class ProcessorStatus(str, Enum):
    """Processor status states."""
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class AdapterStatus(str, Enum):
    """Adapter status states."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOADING = "loading"
    ERROR = "error"


class ConfigScope(str, Enum):
    """Configuration scope levels."""
    RUNTIME = "runtime"      # Runtime-only changes (not persisted)
    SESSION = "session"      # Session-level changes (persisted until restart)
    PERSISTENT = "persistent" # Persistent changes (written to file)


class ConfigValidationLevel(str, Enum):
    """Configuration validation levels."""
    STRICT = "strict"        # Full validation, reject invalid configs
    LENIENT = "lenient"      # Validation with warnings, allow minor issues
    BYPASS = "bypass"        # Skip validation (dangerous, admin only)


# Request/Response Schemas
class ProcessorControlRequest(BaseModel):
    """Request for processor control operations."""
    action: str = Field(..., description="Action to perform: step, pause, resume")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")


class ProcessorControlResponse(BaseModel):
    """Response from processor control operations."""
    success: bool
    action: str
    timestamp: datetime
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class AdapterLoadRequest(BaseModel):
    """Request to load a new adapter."""
    adapter_type: str = Field(..., description="Type of adapter (discord, cli, api)")
    adapter_id: str = Field(..., description="Unique identifier for this adapter instance")
    config: Dict[str, Any] = Field(..., description="Adapter configuration")
    auto_start: bool = Field(default=True, description="Start adapter immediately after loading")


class AdapterUnloadRequest(BaseModel):
    """Request to unload an adapter."""
    adapter_id: str = Field(..., description="Unique identifier of adapter to unload")
    force: bool = Field(default=False, description="Force unload even if adapter is busy")


class AdapterOperationResponse(BaseModel):
    """Response from adapter operations."""
    success: bool
    adapter_id: str
    adapter_type: str
    timestamp: datetime
    status: AdapterStatus
    message: Optional[str] = None
    error: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration."""
    path: str = Field(..., description="Configuration path using dot notation (e.g., 'llm_services.openai.model_name')")
    value: Any = Field(..., description="New value for the configuration")
    scope: ConfigScope = Field(default=ConfigScope.RUNTIME, description="Scope of the configuration change")
    validation_level: ConfigValidationLevel = Field(default=ConfigValidationLevel.STRICT, description="Validation level")
    reason: Optional[str] = Field(None, description="Reason for the configuration change")


class ConfigGetRequest(BaseModel):
    """Request to get configuration values."""
    path: Optional[str] = Field(None, description="Configuration path, null for entire config")
    include_sensitive: bool = Field(default=False, description="Include sensitive values (requires auth)")


class ProfileReloadRequest(BaseModel):
    """Request to reload an agent profile."""
    profile_name: str = Field(..., description="Name of the profile to load")
    config_path: Optional[str] = Field(None, description="Optional custom config path")
    scope: ConfigScope = Field(default=ConfigScope.SESSION, description="Scope of the profile change")


class ConfigValidationRequest(BaseModel):
    """Request to validate configuration."""
    config_data: Dict[str, Any] = Field(..., description="Configuration data to validate")
    config_path: Optional[str] = Field(None, description="Path within configuration")


class ConfigOperationResponse(BaseModel):
    """Response from configuration operations."""
    success: bool
    operation: str
    timestamp: datetime
    path: Optional[str] = None
    old_value: Any = None
    new_value: Any = None
    scope: Optional[ConfigScope] = None
    message: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class ConfigValidationResponse(BaseModel):
    """Response from configuration validation."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class RuntimeStatusResponse(BaseModel):
    """Response with current runtime status."""
    processor_status: ProcessorStatus
    active_adapters: List[str]
    loaded_adapters: List[str]
    current_profile: str
    config_scope: ConfigScope
    uptime_seconds: float
    last_config_change: Optional[datetime] = None


class AdapterInfo(BaseModel):
    """Information about an adapter."""
    adapter_id: str
    adapter_type: str
    status: AdapterStatus
    config: Dict[str, Any]
    capabilities: List[str] = Field(default_factory=list)
    channels: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    load_time: datetime
    last_activity: Optional[datetime] = None


class RuntimeStateSnapshot(BaseModel):
    """Complete runtime state snapshot."""
    timestamp: datetime
    processor_status: ProcessorStatus
    adapters: List[AdapterInfo]
    configuration: Dict[str, Any]
    active_profile: str
    loaded_profiles: List[str]
    uptime_seconds: float
    memory_usage_mb: float
    system_health: str


# Agent Profile Management Schemas
class AgentProfileInfo(BaseModel):
    """Information about an agent profile."""
    name: str
    description: Optional[str] = None
    file_path: str
    is_active: bool
    permitted_actions: List[str] = Field(default_factory=list)
    adapter_configs: Dict[str, Any] = Field(default_factory=dict)
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None


class AgentProfileCreateRequest(BaseModel):
    """Request to create a new agent profile."""
    name: str = Field(..., description="Profile name")
    description: Optional[str] = Field(None, description="Profile description")
    base_profile: Optional[str] = Field(None, description="Base profile to inherit from")
    config: Dict[str, Any] = Field(..., description="Profile configuration")
    save_to_file: bool = Field(default=True, description="Save profile to file")


class AgentProfileUpdateRequest(BaseModel):
    """Request to update an agent profile."""
    name: str = Field(..., description="Profile name to update")
    config_updates: Dict[str, Any] = Field(..., description="Configuration updates to apply")
    merge_strategy: str = Field(default="merge", description="How to apply updates: merge, replace")
    save_to_file: bool = Field(default=True, description="Save changes to file")


class AgentProfileResponse(BaseModel):
    """Response from agent profile operations."""
    success: bool
    profile_name: str
    operation: str
    timestamp: datetime
    message: Optional[str] = None
    error: Optional[str] = None
    profile_info: Optional[AgentProfileInfo] = None


class ConfigBackupRequest(BaseModel):
    """Request to backup configuration."""
    include_profiles: bool = Field(default=True, description="Include agent profiles")
    backup_name: Optional[str] = Field(None, description="Custom backup name")


class ConfigRestoreRequest(BaseModel):
    """Request to restore configuration."""
    backup_name: str = Field(..., description="Name of backup to restore")
    restore_profiles: bool = Field(default=True, description="Restore agent profiles")
    restart_required: bool = Field(default=True, description="Whether restart is required")


class ConfigBackupResponse(BaseModel):
    """Response from configuration backup/restore operations."""
    success: bool
    operation: str
    backup_name: str
    timestamp: datetime
    files_included: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    error: Optional[str] = None
