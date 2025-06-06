from enum import Enum
from typing import List
from pydantic import BaseModel, Field, ConfigDict

__all__ = [
    "ResourceAction",
    "ResourceLimit",
    "ResourceBudget",
    "ResourceSnapshot",
]


class ResourceAction(str, Enum):
    """Actions to take when a resource limit is exceeded."""

    LOG = "log"
    WARN = "warn"
    THROTTLE = "throttle"
    DEFER = "defer"
    REJECT = "reject"
    SHUTDOWN = "shutdown"


class ResourceLimit(BaseModel):
    """Configuration for a single resource."""

    limit: int = Field(description="Hard limit value")
    warning: int = Field(description="Warning threshold")
    critical: int = Field(description="Critical threshold")
    action: ResourceAction = ResourceAction.DEFER
    cooldown_seconds: int = 60

    model_config = ConfigDict(extra="forbid")


class ResourceBudget(BaseModel):
    """Limits for all monitored resources."""

    memory_mb: ResourceLimit = Field(
        default_factory=lambda: ResourceLimit(limit=256, warning=200, critical=240)
    )
    cpu_percent: ResourceLimit = Field(
        default_factory=lambda: ResourceLimit(limit=80, warning=60, critical=75, action=ResourceAction.THROTTLE)
    )
    tokens_hour: ResourceLimit = Field(
        default_factory=lambda: ResourceLimit(limit=10000, warning=8000, critical=9500)
    )
    tokens_day: ResourceLimit = Field(
        default_factory=lambda: ResourceLimit(limit=100000, warning=80000, critical=95000, action=ResourceAction.REJECT)
    )
    disk_mb: ResourceLimit = Field(
        default_factory=lambda: ResourceLimit(limit=100, warning=80, critical=95, action=ResourceAction.WARN)
    )
    thoughts_active: ResourceLimit = Field(
        default_factory=lambda: ResourceLimit(limit=50, warning=40, critical=48)
    )

    model_config = ConfigDict(extra="forbid")


class ResourceSnapshot(BaseModel):
    """Current resource usage snapshot."""

    memory_mb: int = 0
    memory_percent: int = 0
    cpu_percent: int = 0
    cpu_average_1m: int = 0
    tokens_used_hour: int = 0
    tokens_used_day: int = 0
    disk_used_mb: int = 0
    disk_free_mb: int = 0
    thoughts_active: int = 0
    thoughts_queued: int = 0
    healthy: bool = True
    warnings: List[str] = Field(default_factory=list)
    critical: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")
