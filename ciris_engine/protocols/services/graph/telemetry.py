"""Telemetry Service Protocol."""

from typing import Protocol, Any, Dict, List, Optional
from abc import abstractmethod
from datetime import datetime

from ...runtime.base import GraphServiceProtocol

class TelemetryServiceProtocol(GraphServiceProtocol, Protocol):
    """Protocol for telemetry service."""

    @abstractmethod
    async def record_metric(self, metric_name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None, handler_name: Optional[str] = None) -> None:
        """Record a telemetry metric."""
        ...

    @abstractmethod
    async def query_metrics(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """Query metrics."""
        ...

    @abstractmethod
    async def get_metric_summary(self, metric_name: str, window_minutes: int = 60) -> Dict[str, float]:
        """Get metric summary statistics."""
        ...
    
    @abstractmethod
    async def get_metric_count(self) -> int:
        """Get total count of metrics stored."""
        ...
    
    @abstractmethod
    async def get_telemetry_summary(self) -> Any:  # Should be TelemetrySummary but avoiding circular import
        """Get comprehensive telemetry summary."""
        ...
