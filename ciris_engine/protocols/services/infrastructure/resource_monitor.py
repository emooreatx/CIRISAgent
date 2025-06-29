"""
Protocol for Resource Monitor Service.

Monitors system resources, enforces limits, and triggers protective actions
for 1000-year sustainable operation.
"""

from typing import Protocol, TYPE_CHECKING, runtime_checkable

from ...runtime.base import ServiceProtocol

# Import forward references
if TYPE_CHECKING:
    from ciris_engine.schemas.services.infrastructure.resource_monitor import (
        ResourceBudget, ResourceSnapshot
    )

@runtime_checkable
class ResourceMonitorServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for resource monitoring service.

    Tracks CPU, memory, disk, token usage and active thoughts.
    Enforces limits through throttle, defer, reject, and shutdown signals.
    Critical for preventing resource exhaustion over centuries of operation.
    """

    budget: "ResourceBudget"
    snapshot: "ResourceSnapshot"

    async def start(self) -> None:
        """Start resource monitoring with periodic checks."""
        ...

    async def stop(self) -> None:
        """Stop resource monitoring gracefully."""
        ...

    async def record_tokens(self, tokens: int) -> None:
        """Record token usage for rate limiting.

        Args:
            tokens: Number of tokens consumed
        """
        ...

    async def check_available(self, resource: str, amount: int = 0) -> bool:
        """Check if resource is available before consuming.

        Args:
            resource: Resource name (memory_mb, tokens_hour, thoughts_active)
            amount: Additional amount to be consumed

        Returns:
            True if resource is available, False if would exceed warning threshold
        """
        ...
