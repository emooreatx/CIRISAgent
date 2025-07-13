"""
Base Graph Service - Common implementation for all graph services.

Provides default implementations of GraphServiceProtocol methods.
All graph services use the MemoryBus for actual persistence operations.
"""
from typing import List, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
import logging

from ciris_engine.protocols.runtime.base import GraphServiceProtocol
from ciris_engine.schemas.services.graph_core import GraphNode
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpStatus
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

if TYPE_CHECKING:
    from ciris_engine.logic.buses import MemoryBus

logger = logging.getLogger(__name__)

class BaseGraphService(ABC, GraphServiceProtocol):
    """Base class for all graph services providing common functionality.

    Graph services store their data through the MemoryBus, which provides:
    - Multiple backend support (Neo4j, ArangoDB, in-memory)
    - Secret detection and encryption
    - Audit trail integration
    - Typed schema validation
    """

    def __init__(self, memory_bus: Optional['MemoryBus'] = None, time_service: Optional[TimeServiceProtocol] = None) -> None:
        """Initialize base graph service.

        Args:
            memory_bus: MemoryBus for graph persistence operations
            time_service: TimeService for consistent timestamps
        """
        self._started = False
        self.service_name = self.__class__.__name__
        self._memory_bus = memory_bus
        self._time_service = time_service

    def _set_memory_bus(self, memory_bus: 'MemoryBus') -> None:
        """Set the memory bus for graph operations."""
        self._memory_bus = memory_bus

    def _set_time_service(self, time_service: TimeServiceProtocol) -> None:
        """Set the time service for timestamps."""
        self._time_service = time_service

    async def start(self) -> None:
        """Start the service."""
        self._started = True
        logger.info(f"{self.service_name} started")

    async def stop(self) -> None:
        """Stop the service."""
        self._started = False
        logger.info(f"{self.service_name} stopped")

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name=self.service_name,
            actions=[
                "store_in_graph",
                "query_graph",
                self.get_node_type()
            ],
            version="1.0.0"
        )

    def get_status(self) -> ServiceStatus:
        """Get current service status."""
        return ServiceStatus(
            service_name=self.service_name,
            service_type=self.get_node_type(),
            is_healthy=self._started and self._memory_bus is not None,
            uptime_seconds=0.0,  # Would need to track start time for real uptime
            metrics={
                "memory_bus_available": 1.0 if self._memory_bus is not None else 0.0,
                "time_service_available": 1.0 if self._time_service is not None else 0.0
            }
        )

    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._started and self._memory_bus is not None

    async def store_in_graph(self, node: GraphNode) -> str:
        """Store a node in the graph using MemoryBus.

        Args:
            node: GraphNode to store (or any object with to_graph_node method)

        Returns:
            Node ID if successful, empty string if failed
        """
        if not self._memory_bus:
            raise RuntimeError(f"{self.service_name}: Memory bus not available")

        # Convert to GraphNode if it has a to_graph_node method
        if hasattr(node, 'to_graph_node') and callable(getattr(node, 'to_graph_node')):
            graph_node = node.to_graph_node()
        else:
            graph_node = node

        result = await self._memory_bus.memorize(graph_node)
        return graph_node.id if result.status == MemoryOpStatus.OK else ""

    async def query_graph(self, query: MemoryQuery) -> List[GraphNode]:
        """Query the graph using MemoryBus.

        Args:
            query: MemoryQuery with filters and options

        Returns:
            List of matching GraphNodes
        """
        if not self._memory_bus:
            logger.warning(f"{self.service_name}: Memory bus not available for query")
            return []

        result = await self._memory_bus.recall(query)

        # Handle different result types
        if hasattr(result, 'status') and hasattr(result, 'data'):
            # It's a MemoryOpResult
            if result.status == MemoryOpStatus.OK and result.data:
                if isinstance(result.data, list):
                    return result.data
                else:
                    return [result.data]
        elif isinstance(result, list):
            # Direct list of nodes
            return result

        return []

    @abstractmethod
    def get_node_type(self) -> str:
        """Get the type of nodes this service manages - must be implemented by subclass."""
        raise NotImplementedError
