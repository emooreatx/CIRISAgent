"""Memory Service Protocol."""

from typing import Protocol, List, Optional, Dict
from abc import abstractmethod

from ...runtime.base import GraphServiceProtocol
from ciris_engine.schemas.services.graph_core import GraphNode
from ciris_engine.schemas.services.operations import MemoryOpResult, MemoryQuery
from ciris_engine.schemas.runtime.memory import TimeSeriesDataPoint
from ciris_engine.schemas.services.graph.memory import MemorySearchFilter

class MemoryServiceProtocol(GraphServiceProtocol, Protocol):
    """Protocol for memory service - the three universal memory verbs."""

    @abstractmethod
    async def memorize(self, node: GraphNode) -> MemoryOpResult:
        """MEMORIZE - Store a graph node in memory."""
        ...

    @abstractmethod
    async def recall(self, recall_query: MemoryQuery) -> List[GraphNode]:
        """RECALL - Retrieve nodes matching query."""
        ...

    @abstractmethod
    async def forget(self, node: GraphNode) -> MemoryOpResult:
        """FORGET - Remove a specific node from memory."""
        ...

    @abstractmethod
    async def memorize_metric(self, metric_name: str, value: float,
                             tags: Optional[Dict[str, str]] = None, scope: str = "local") -> MemoryOpResult:
        """Memorize a metric value (convenience for telemetry)."""
        ...

    @abstractmethod
    async def memorize_log(self, log_message: str, log_level: str = "INFO",
                          tags: Optional[Dict[str, str]] = None, scope: str = "local") -> MemoryOpResult:
        """Memorize a log entry (convenience for logging)."""
        ...

    @abstractmethod
    async def recall_timeseries(self, scope: str = "default", hours: int = 24,
                               correlation_types: Optional[List[str]] = None) -> List[TimeSeriesDataPoint]:
        """Recall time-series data."""
        ...

    @abstractmethod
    async def export_identity_context(self) -> str:
        """Export identity nodes as string representation."""
        ...

    @abstractmethod
    async def search(self, query: str, filters: Optional['MemorySearchFilter'] = None) -> List[GraphNode]:
        """Search memories using text query."""
        ...
