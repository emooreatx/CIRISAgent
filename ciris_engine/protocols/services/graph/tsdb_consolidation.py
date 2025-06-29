"""
Protocol for TSDB Consolidation Service.

This service consolidates time-series telemetry data into permanent summaries
for long-term memory (1000+ years).
"""

from typing import Protocol, runtime_checkable, Optional, TYPE_CHECKING
from datetime import datetime

from ...runtime.base import GraphServiceProtocol

if TYPE_CHECKING:
    from ciris_engine.schemas.services.nodes import TSDBSummary

@runtime_checkable
class TSDBConsolidationServiceProtocol(GraphServiceProtocol, Protocol):
    """Protocol for TSDB consolidation service.

    Consolidates TSDB telemetry nodes into 6-hour summaries for permanent storage.
    Runs every 6 hours and deletes raw nodes older than 24 hours.
    """

    async def start(self) -> None:
        """Start the consolidation service and begin periodic consolidation."""
        ...

    async def stop(self) -> None:
        """Stop the consolidation service gracefully, running final consolidation."""
        ...

    async def get_summary_for_period(self, period_start: datetime) -> Optional["TSDBSummary"]:
        """Retrieve a TSDBSummary for a specific period.

        Args:
            period_start: Start of the 6-hour period

        Returns:
            TSDBSummary if found, None otherwise
        """
        ...
