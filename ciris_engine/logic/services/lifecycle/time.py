"""
Secure Time Service for CIRIS Trinity Architecture.

Provides centralized time operations that are:
- Mockable for testing
- Timezone-aware (always UTC)
- Consistent across the system
- No direct datetime.now() usage allowed

This replaces the time_utils.py utility with a proper service.
"""
from datetime import datetime, timezone

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus

class TimeService(TimeServiceProtocol, ServiceProtocol):
    """Secure time service implementation."""

    def __init__(self) -> None:
        """Initialize the time service."""
        self._start_time = datetime.now(timezone.utc)
        self._running = False

    async def start(self) -> None:
        """Start the service."""
        self._running = True
        self._start_time = datetime.now(timezone.utc)

    async def stop(self) -> None:
        """Stop the service."""
        self._running = False

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="TimeService",
            actions=["now", "now_iso", "timestamp"],
            version="1.0.0",
            dependencies=[],
            metadata={"description": "Provides consistent UTC time operations"}
        )

    def get_status(self) -> ServiceStatus:
        """Get service status."""
        uptime = (self.now() - self._start_time).total_seconds()
        return ServiceStatus(
            service_name="TimeService",
            service_type="infrastructure",
            is_healthy=self._running,
            uptime_seconds=uptime,
            metrics={},
            last_error=None,
            last_health_check=self.now() if self._running else None
        )

    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._running

    def now(self) -> datetime:
        """
        Get current time in UTC.

        Returns:
            datetime: Current time in UTC with timezone info
        """
        return datetime.now(timezone.utc)

    def now_iso(self) -> str:
        """
        Get current time as ISO string.

        Returns:
            str: Current UTC time in ISO format
        """
        return self.now().isoformat()

    def timestamp(self) -> float:
        """
        Get current Unix timestamp.

        Returns:
            float: Seconds since Unix epoch
        """
        return self.now().timestamp()

    async def get_uptime(self) -> float:
        """
        Get service uptime in seconds.

        Returns:
            float: Uptime in seconds since service start
        """
        return (self.now() - self._start_time).total_seconds()
