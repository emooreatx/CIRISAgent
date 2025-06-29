"""
Schemas for Time Service.

Provides configuration and data structures for time operations.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TimeServiceConfig(BaseModel):
    """Configuration for Time Service."""

    enable_mocking: bool = Field(
        default=True,
        description="Whether to allow time mocking for tests"
    )
    default_timezone: str = Field(
        default="UTC",
        description="Default timezone (always UTC for CIRIS)"
    )

class TimeSnapshot(BaseModel):
    """A snapshot of time information."""

    current_time: datetime = Field(..., description="Current time in UTC")
    current_iso: str = Field(..., description="Current time as ISO string")
    current_timestamp: float = Field(..., description="Current Unix timestamp")
    is_mocked: bool = Field(..., description="Whether time is mocked")
    mock_time: Optional[datetime] = Field(None, description="Mock time if set")

class TimeServiceStatus(BaseModel):
    """Extended status for Time Service."""

    service_name: str = Field(default="TimeService")
    is_healthy: bool = Field(..., description="Service health")
    uptime_seconds: float = Field(..., description="Service uptime")
    is_mocked: bool = Field(..., description="Whether time is mocked")
    calls_served: int = Field(default=0, description="Total time requests served")
