"""API-specific schemas for request/response validation."""
from typing import List, Optional, Dict
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
    id: str = Field(..., description="Message ID")
    content: str = Field(..., description="Message content")
    channel_id: str = Field(..., description="Channel ID")
    author_id: str = Field(..., description="Author ID")
    author_name: str = Field(..., description="Author display name")
    timestamp: datetime = Field(..., description="Message timestamp")
    is_bot: bool = Field(False, description="Whether message is from bot")


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