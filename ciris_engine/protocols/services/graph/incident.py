"""
Protocol for Incident Management Service.

ITIL-aligned incident processing for agent self-improvement through
pattern detection and insight generation.
"""

from typing import List, Protocol, TYPE_CHECKING, runtime_checkable

from ...runtime.base import GraphServiceProtocol

# Import forward reference since schema might not exist yet
if TYPE_CHECKING:
    from ciris_engine.schemas.services.graph.incident import IncidentInsightNode
    from ciris_engine.schemas.services.core import ServiceCapabilities

@runtime_checkable
class IncidentManagementServiceProtocol(GraphServiceProtocol, Protocol):
    """Protocol for incident management service.

    Processes incidents from logs, detects patterns, identifies problems,
    and generates insights for continuous self-improvement.
    """

    async def process_recent_incidents(self, hours: int = 24) -> "IncidentInsightNode":
        """Process recent incidents to identify patterns and generate insights.

        Called during dream cycle for self-improvement analysis.

        Args:
            hours: Number of hours of incidents to analyze

        Returns:
            IncidentInsightNode with analysis results and recommendations
        """
        ...

    async def start(self) -> None:
        """Start the incident management service."""
        ...

    async def stop(self) -> None:
        """Stop the incident management service."""
        ...

    def get_capabilities(self) -> ServiceCapabilities:
        """Return service capabilities."""
        ...
