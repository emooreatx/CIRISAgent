"""
Protocol for TSDB Consolidation Service.

This service consolidates time-series telemetry data into permanent summaries
for long-term memory (1000+ years).
"""

from typing import Protocol, runtime_checkable, Optional, TYPE_CHECKING, Dict, Any
from datetime import datetime
from abc import abstractmethod

from ...runtime.base import GraphServiceProtocol

if TYPE_CHECKING:
    from ciris_engine.schemas.services.graph_core import NodeType
    from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus

@runtime_checkable
class TSDBConsolidationServiceProtocol(GraphServiceProtocol, Protocol):
    """Protocol for TSDB consolidation service.

    Consolidates TSDB telemetry nodes into 6-hour summaries for permanent storage.
    Runs every 6 hours and deletes raw nodes older than 24 hours.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the consolidation service and begin periodic consolidation."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the consolidation service gracefully, running final consolidation."""
        ...

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the service is healthy.
        
        Returns:
            True if service is running and has required dependencies
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> "ServiceCapabilities":
        """Get service capabilities.
        
        Returns:
            ServiceCapabilities with actions, version, dependencies, and metadata
        """
        ...

    @abstractmethod
    def get_status(self) -> "ServiceStatus":
        """Get service status.
        
        Returns:
            ServiceStatus with health, uptime, metrics, and last consolidation info
        """
        ...

    @abstractmethod
    def get_node_type(self) -> "NodeType":
        """Get the node type this service manages.
        
        Returns:
            NodeType.TSDB_SUMMARY
        """
        ...

    @abstractmethod
    async def get_summary_for_period(self, period_start: datetime, period_end: datetime) -> Optional[Dict[str, Any]]:
        """Get the summary for a specific period.

        Args:
            period_start: Start of the period
            period_end: End of the period

        Returns:
            Dictionary containing summary data if found, including:
            - metrics: Aggregated metrics for the period
            - total_tokens: Total tokens used
            - total_cost_cents: Total cost in cents
            - total_carbon_grams: Total carbon emissions
            - total_energy_kwh: Total energy consumption
            - action_counts: Counts by action type
            - source_node_count: Number of source nodes
            - period_start/end/label: Period information
            - conversations: Conversation summaries
            - traces: Trace summaries
            - audits: Audit summaries
            - tasks: Task summaries
            - memories: Memory references
        """
        ...
