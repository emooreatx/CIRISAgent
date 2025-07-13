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
from typing import List, Dict, Any, Optional

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.logic.services.base_infrastructure_service import BaseInfrastructureService
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.services.metadata import ServiceMetadata

class TimeService(BaseInfrastructureService, TimeServiceProtocol):
    """Secure time service implementation."""

    def __init__(self) -> None:
        """Initialize the time service."""
        # Initialize base class without time_service (we ARE the time service)
        super().__init__(service_name="TimeService", version="1.0.0")
        self._start_time = datetime.now(timezone.utc)

    # Required abstract methods from BaseService

    def get_service_type(self) -> ServiceType:
        """Get the service type enum value."""
        return ServiceType.TIME

    def _get_actions(self) -> List[str]:
        """Get list of actions this service provides."""
        return ["now", "now_iso", "timestamp"]

    def _check_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        # TimeService has no dependencies
        return True

    def get_capabilities(self) -> "ServiceCapabilities":
        """Get service capabilities with custom metadata."""
        # Get parent capabilities which includes infrastructure metadata
        capabilities = super().get_capabilities()
        
        # Add our specific metadata
        capabilities.metadata.update({
            "description": "Provides consistent UTC time operations"
        })
        
        return capabilities

    # Override _now to prevent circular dependency
    def _now(self) -> datetime:
        """Get current time without using time service."""
        return datetime.now(timezone.utc)

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
    
    def get_uptime(self) -> float:
        """
        Get service uptime in seconds.
        
        Returns:
            float: Seconds since service started
        """
        if self._start_time is None:
            return 0.0
        return (self.now() - self._start_time).total_seconds()
