"""
Memory message bus - handles all memory service operations
"""

import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.schemas.graph_schemas_v1 import GraphNode
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult, MemoryOpStatus, MemoryQuery
from ciris_engine.schemas.protocol_schemas_v1 import MemorySearchResult, TimeSeriesDataPoint, IdentityUpdateRequest, EnvironmentUpdateRequest
from ciris_engine.protocols.services import MemoryService
from .base_bus import BaseBus, BusMessage

logger = logging.getLogger(__name__)


@dataclass
class MemorizeRequest(BusMessage):
    """Request to memorize a node"""
    node: GraphNode


@dataclass
class RecallRequest(BusMessage):
    """Request to recall a node"""
    node: GraphNode


@dataclass
class ForgetRequest(BusMessage):
    """Request to forget a node"""
    node: GraphNode


class MemoryBus(BaseBus[MemoryService]):
    """
    Message bus for all memory operations.
    
    Handles:
    - memorize
    - recall
    - forget
    """
    
    def __init__(self, service_registry: Any):
        super().__init__(
            service_type=ServiceType.MEMORY,
            service_registry=service_registry
        )
    
    async def memorize(
        self,
        node: GraphNode,
        handler_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryOpResult:
        """
        Memorize a node.
        
        This is always synchronous as handlers need the result.
        """
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["memorize"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason="No memory service available",
                data=node.model_dump() if hasattr(node, 'model_dump') else None
            )
            
        try:
            result = await service.memorize(node)
            # Protocol guarantees MemoryOpResult return
            return result
        except Exception as e:
            logger.error(f"Failed to memorize node: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
    async def recall(
        self,
        recall_query: MemoryQuery,
        handler_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[GraphNode]:
        """
        Recall nodes based on query.
        
        This is always synchronous as handlers need the result.
        """
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["recall"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return []
            
        try:
            nodes = await service.recall(recall_query)
            return nodes if nodes else []
        except Exception as e:
            logger.error(f"Failed to recall nodes: {e}", exc_info=True)
            return []
    
    async def forget(
        self,
        node: GraphNode,
        handler_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryOpResult:
        """
        Forget a node.
        
        This is always synchronous as handlers need the result.
        """
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["forget"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason="No memory service available",
                data=node.model_dump() if hasattr(node, 'model_dump') else None
            )
            
        try:
            result = await service.forget(node)
            # Protocol guarantees MemoryOpResult return
            return result
        except Exception as e:
            logger.error(f"Failed to forget node: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
    async def search_memories(
        self,
        query: str,
        scope: str = "default",
        limit: int = 10,
        handler_name: str = "default"
    ) -> List[MemorySearchResult]:
        """Search memories using text query."""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["search_memories"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return []
            
        try:
            return await service.search_memories(query, scope, limit)
        except Exception as e:
            logger.error(f"Failed to search memories: {e}", exc_info=True)
            return []
    
    async def recall_timeseries(
        self,
        scope: str = "default",
        hours: int = 24,
        correlation_types: Optional[List[str]] = None,
        handler_name: str = "default"
    ) -> List[TimeSeriesDataPoint]:
        """Recall time-series data."""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["recall_timeseries"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return []
            
        try:
            return await service.recall_timeseries(scope, hours, correlation_types)
        except Exception as e:
            logger.error(f"Failed to recall timeseries: {e}", exc_info=True)
            return []
    
    async def memorize_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        scope: str = "local",
        handler_name: str = "default"
    ) -> MemoryOpResult:
        """Memorize a metric as both graph node and TSDB correlation."""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["memorize_metric"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason="No memory service available"
            )
            
        try:
            return await service.memorize_metric(metric_name, value, tags, scope)
        except Exception as e:
            logger.error(f"Failed to memorize metric: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
    async def memorize_log(
        self,
        log_message: str,
        log_level: str = "INFO",
        tags: Optional[Dict[str, str]] = None,
        scope: str = "local",
        handler_name: str = "default"
    ) -> MemoryOpResult:
        """Memorize a log entry as both graph node and TSDB correlation."""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["memorize_log"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason="No memory service available"
            )
            
        try:
            return await service.memorize_log(log_message, log_level, tags, scope)
        except Exception as e:
            logger.error(f"Failed to memorize log: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
    async def export_identity_context(
        self,
        handler_name: str = "default"
    ) -> str:
        """Export identity nodes as string representation."""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["export_identity_context"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return ""
            
        try:
            return await service.export_identity_context()
        except Exception as e:
            logger.error(f"Failed to export identity context: {e}", exc_info=True)
            return ""
    
    async def update_identity_graph(
        self,
        update_data: IdentityUpdateRequest,
        handler_name: str = "default"
    ) -> MemoryOpResult:
        """Update identity graph nodes based on WA feedback."""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["update_identity_graph"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason="No memory service available"
            )
            
        try:
            return await service.update_identity_graph(update_data)
        except Exception as e:
            logger.error(f"Failed to update identity graph: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
    async def update_environment_graph(
        self,
        update_data: EnvironmentUpdateRequest,
        handler_name: str = "default"
    ) -> MemoryOpResult:
        """Update environment graph based on WA feedback."""
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["update_environment_graph"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason="No memory service available"
            )
            
        try:
            return await service.update_environment_graph(update_data)
        except Exception as e:
            logger.error(f"Failed to update environment graph: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
    async def is_healthy(self, handler_name: str = "default") -> bool:
        """Check if memory service is healthy."""
        service = await self.get_service(handler_name=handler_name)
        if not service:
            return False
        try:
            return await service.is_healthy()
        except Exception as e:
            logger.error(f"Failed to check health: {e}")
            return False
    
    async def get_capabilities(self, handler_name: str = "default") -> List[str]:
        """Get memory service capabilities."""
        service = await self.get_service(handler_name=handler_name)
        if not service:
            return []
        try:
            return await service.get_capabilities()
        except Exception as e:
            logger.error(f"Failed to get capabilities: {e}")
            return []
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process a memory message"""
        # For now, all memory operations are synchronous
        # This bus mainly exists for consistency and future async operations
        logger.warning(f"Memory operations should be synchronous, got queued message: {type(message)}")