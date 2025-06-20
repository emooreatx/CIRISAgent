"""API-specific schemas for request/response validation."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from .foundational_schemas_v1 import ServiceType


class MessageRequest(BaseModel):
    """Request schema for sending messages."""
    content: str = Field(..., description="Message content")
    channel_id: str = Field(..., description="Channel ID to send to")
    author_id: Optional[str] = Field("api_user", description="Author ID")
    author_name: Optional[str] = Field("API User", description="Display name")


class MessageResponse(BaseModel):
    """Response schema for message operations."""
    status: str = Field(..., description="Message status")
    message_id: str = Field(..., description="Message ID")
    channel_id: str = Field(..., description="Channel ID")
    timestamp: str = Field(..., description="Message timestamp")


class MessageListResponse(BaseModel):
    """Response schema for listing messages."""
    messages: List[MessageResponse] = Field(..., description="List of messages")
    channel_id: str = Field(..., description="Channel ID")
    count: int = Field(..., description="Number of messages returned")


class ServiceProvider(BaseModel):
    """Schema for a service provider."""
    provider: str = Field(..., description="Provider name")
    handler: str = Field(..., description="Handler name or 'global'")
    priority: str = Field(..., description="Priority level")
    capabilities: List[str] = Field(..., description="Provider capabilities")
    is_global: bool = Field(False, description="Whether this is a global service")


class ServicesResponse(BaseModel):
    """Response schema for services listing."""
    services: Dict[str, List[ServiceProvider]] = Field(..., description="Services by type")
    timestamp: datetime = Field(..., description="Response timestamp")


class RuntimeStatus(BaseModel):
    """Schema for runtime status."""
    state: str = Field(..., description="Current runtime state")
    uptime_seconds: float = Field(..., description="Uptime in seconds")
    version: str = Field(..., description="Runtime version")


class RuntimeStatusResponse(BaseModel):
    """Response schema for runtime status."""
    status: RuntimeStatus = Field(..., description="Runtime status")
    timestamp: datetime = Field(..., description="Response timestamp")


class HealthResponse(BaseModel):
    """Response schema for health check."""
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Current timestamp")
    runtime_state: Optional[str] = Field(None, description="Current runtime state")


class ErrorResponse(BaseModel):
    """Response schema for errors."""
    error: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp")


class ChannelInfo(BaseModel):
    """Schema for channel information."""
    channel_id: str = Field(..., description="Channel ID")
    message_count: int = Field(..., description="Total messages in channel")
    unique_authors: int = Field(..., description="Number of unique authors")
    created_at: str = Field(..., description="Channel creation time")
    last_activity: str = Field(..., description="Last activity time")


class AgentStatus(BaseModel):
    """Schema for agent status."""
    online: bool = Field(..., description="Whether agent is online")
    timestamp: str = Field(..., description="Status timestamp")
    identity: Optional[Dict[str, Any]] = Field(None, description="Agent identity info")
    processor: Optional[Dict[str, Any]] = Field(None, description="Processor status")
    active_channels: int = Field(..., description="Number of active channels")