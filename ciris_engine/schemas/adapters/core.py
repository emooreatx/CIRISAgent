"""
API Schemas v1 - Request/response schemas for CIRIS API

Provides schemas for API endpoints including messages, services, status, and health.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from ciris_engine.schemas.runtime.enums import ServiceType

class MessageRequest(BaseModel):
    """Request schema for sending messages"""
    content: str = Field(description="Message content")
    channel_id: str = Field(description="Channel ID to send to")
    author_id: Optional[str] = Field(default="api_user", description="Author ID")
    author_name: Optional[str] = Field(default="API User", description="Display name")

    model_config = ConfigDict(extra = "forbid")

class MessageResponse(BaseModel):
    """Response schema for message operations"""
    status: str = Field(description="Message status")
    message_id: str = Field(description="Message ID")
    channel_id: str = Field(description="Channel ID")
    timestamp: datetime = Field(description="Message timestamp")
    content: Optional[str] = Field(default=None, description="Message content")
    author_id: Optional[str] = Field(default=None, description="Message author ID")
    author_name: Optional[str] = Field(default=None, description="Message author name")

    model_config = ConfigDict(extra = "forbid")

class MessageListResponse(BaseModel):
    """Response schema for listing messages"""
    messages: List[MessageResponse] = Field(description="List of messages")
    channel_id: str = Field(description="Channel ID")
    count: int = Field(description="Number of messages returned")

    model_config = ConfigDict(extra = "forbid")

class ServiceProvider(BaseModel):
    """Schema for a service provider"""
    provider: str = Field(description="Provider name")
    handler: str = Field(description="Handler name or 'global'")
    priority: str = Field(description="Priority level")
    capabilities: List[str] = Field(description="Provider capabilities")
    is_global: bool = Field(default=False, description="Whether this is a global service")

    model_config = ConfigDict(extra = "forbid")

class ServiceTypeInfo(BaseModel):
    """Information about a service type"""
    service_type: ServiceType = Field(description="Type of service")
    providers: List[ServiceProvider] = Field(description="Available providers")
    total_providers: int = Field(description="Total number of providers")

    model_config = ConfigDict(extra = "forbid")

class ServicesResponse(BaseModel):
    """Response schema for services listing"""
    services: List[ServiceTypeInfo] = Field(description="Services organized by type")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Response timestamp")

    model_config = ConfigDict(extra = "forbid")

class RuntimeStatus(BaseModel):
    """Schema for runtime status"""
    state: str = Field(description="Current runtime state")
    uptime_seconds: float = Field(ge=0.0, description="Uptime in seconds")
    version: str = Field(description="Runtime version")
    start_time: datetime = Field(description="When runtime started")
    
    model_config = ConfigDict(extra = "forbid")

class RuntimeMetrics(BaseModel):
    """Runtime performance metrics"""
    messages_processed: int = Field(ge=0, description="Total messages processed")
    active_tasks: int = Field(ge=0, description="Number of active tasks")
    memory_usage_mb: Optional[float] = Field(default=None, ge=0.0, description="Memory usage in MB")
    cpu_usage_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="CPU usage percentage")
    
    model_config = ConfigDict(extra = "forbid")

class RuntimeStatusResponse(BaseModel):
    """Response schema for runtime status"""
    status: RuntimeStatus = Field(description="Runtime status")
    metrics: Optional[RuntimeMetrics] = Field(default=None, description="Runtime metrics")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Response timestamp")

    model_config = ConfigDict(extra = "forbid")

class HealthResponse(BaseModel):
    """Response schema for health check"""
    status: str = Field(description="Health status (healthy/unhealthy)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Current timestamp")
    runtime_state: Optional[str] = Field(default=None, description="Current runtime state")
    warnings: List[str] = Field(default_factory=list, description="Active warnings")
    errors: List[str] = Field(default_factory=list, description="Active errors")

    model_config = ConfigDict(extra = "forbid")

class ErrorResponse(BaseModel):
    """Response schema for errors"""
    error: str = Field(description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    details: Optional[str] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp")

    model_config = ConfigDict(extra = "forbid")

class ChannelInfo(BaseModel):
    """Schema for channel information"""
    channel_id: str = Field(description="Channel ID")
    message_count: int = Field(ge=0, description="Total messages in channel")
    unique_authors: int = Field(ge=0, description="Number of unique authors")
    created_at: datetime = Field(description="Channel creation time")
    last_activity: datetime = Field(description="Last activity time")
    is_active: bool = Field(description="Whether channel is currently active")

    model_config = ConfigDict(extra = "forbid")

class AgentIdentity(BaseModel):
    """Agent identity information"""
    name: str = Field(description="Agent name")
    template: str = Field(description="Agent template")
    version: str = Field(description="Agent version")
    capabilities: List[str] = Field(description="Agent capabilities")
    
    model_config = ConfigDict(extra = "forbid")

class MessageProcessorMetrics(BaseModel):
    """Message processor status"""
    is_processing: bool = Field(description="Whether processor is active")
    queue_size: int = Field(ge=0, description="Messages in queue")
    processing_rate: float = Field(ge=0.0, description="Messages per second")
    
    model_config = ConfigDict(extra = "forbid")

class AgentStatus(BaseModel):
    """Schema for agent status"""
    online: bool = Field(description="Whether agent is online")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Status timestamp")
    identity: Optional[AgentIdentity] = Field(default=None, description="Agent identity info")
    processor: Optional[MessageProcessorMetrics] = Field(default=None, description="Processor status")
    active_channels: int = Field(ge=0, description="Number of active channels")

    model_config = ConfigDict(extra = "forbid")

class ChannelListResponse(BaseModel):
    """Response for listing channels"""
    channels: List[ChannelInfo] = Field(description="List of channels")
    total_channels: int = Field(ge=0, description="Total number of channels")
    active_channels: int = Field(ge=0, description="Number of active channels")

    model_config = ConfigDict(extra = "forbid")

__all__ = [
    "MessageRequest",
    "MessageResponse",
    "MessageListResponse",
    "ServiceProvider",
    "ServiceTypeInfo",
    "ServicesResponse",
    "RuntimeStatus",
    "RuntimeMetrics",
    "RuntimeStatusResponse",
    "HealthResponse",
    "ErrorResponse",
    "ChannelInfo",
    "AgentIdentity",
    "MessageProcessorMetrics",
    "AgentStatus",
    "ChannelListResponse",
]