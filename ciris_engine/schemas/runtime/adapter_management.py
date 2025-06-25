"""
Schemas for runtime adapter management.

These replace all Dict[str, Any] usage in adapter_manager.py.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic import Field

class AdapterConfig(BaseModel):
    """Configuration for an adapter."""
    adapter_type: str = Field(..., description="Type of adapter (cli, api, discord, etc.)")
    enabled: bool = Field(True, description="Whether adapter is enabled")
    settings: dict = Field(default_factory=dict, description="Adapter-specific settings")

class AdapterLoadRequest(BaseModel):
    """Request to load an adapter."""
    adapter_type: str = Field(..., description="Type of adapter to load")
    adapter_id: str = Field(..., description="Unique ID for the adapter instance")
    config: Optional[dict] = Field(default_factory=dict, description="Configuration parameters")
    auto_start: bool = Field(True, description="Whether to auto-start the adapter")

class AdapterOperationResult(BaseModel):
    """Result of an adapter operation."""
    success: bool = Field(..., description="Whether operation succeeded")
    adapter_id: str = Field(..., description="Adapter ID")
    adapter_type: Optional[str] = Field(None, description="Adapter type")
    message: Optional[str] = Field(None, description="Operation message")
    error: Optional[str] = Field(None, description="Error message if failed")
    details: Optional[dict] = Field(None, description="Additional details")

class AdapterStatus(BaseModel):
    """Status of a single adapter."""
    adapter_id: str = Field(..., description="Unique adapter ID")
    adapter_type: str = Field(..., description="Type of adapter")
    is_running: bool = Field(..., description="Whether adapter is running")
    loaded_at: datetime = Field(..., description="When adapter was loaded")
    services_registered: List[str] = Field(default_factory=list, description="Services registered by adapter")
    config_params: AdapterConfig = Field(..., description="Adapter configuration")
    metrics: Optional[dict] = Field(None, description="Adapter metrics")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")

class AdapterListResponse(BaseModel):
    """Response containing list of adapters."""
    adapters: List[AdapterStatus] = Field(..., description="List of adapter statuses")
    total_count: int = Field(..., description="Total number of adapters")
    running_count: int = Field(..., description="Number of running adapters")

class ServiceRegistrationInfo(BaseModel):
    """Information about a service registration."""
    service_type: str = Field(..., description="Type of service")
    provider_name: str = Field(..., description="Provider name")
    priority: str = Field(..., description="Registration priority")
    capabilities: List[str] = Field(..., description="Service capabilities")

class AdapterMetrics(BaseModel):
    """Metrics for an adapter."""
    messages_processed: int = Field(0, description="Total messages processed")
    errors_count: int = Field(0, description="Total errors")
    uptime_seconds: float = Field(0.0, description="Adapter uptime in seconds")
    last_error: Optional[str] = Field(None, description="Last error message")
    last_error_time: Optional[datetime] = Field(None, description="Last error timestamp")