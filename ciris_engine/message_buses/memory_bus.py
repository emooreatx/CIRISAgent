"""
Memory message bus - handles all memory service operations
"""

import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.schemas.graph_schemas_v1 import GraphNode
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult, MemoryOpStatus
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


class MemoryBus(BaseBus):
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
            # Ensure we return a MemoryOpResult
            if isinstance(result, MemoryOpResult):
                return result
            # Convert to MemoryOpResult if needed
            return MemoryOpResult(
                status=MemoryOpStatus.SUCCESS,
                reason="Memorized successfully",
                data=result if result else None
            )
        except Exception as e:
            logger.error(f"Failed to memorize node: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
    async def recall(
        self,
        node: GraphNode,
        handler_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryOpResult:
        """
        Recall a node.
        
        This is always synchronous as handlers need the result.
        """
        service = await self.get_service(
            handler_name=handler_name,
            required_capabilities=["recall"]
        )
        
        if not service:
            logger.error(f"No memory service available for {handler_name}")
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason="No memory service available",
                data=node.model_dump() if hasattr(node, 'model_dump') else None
            )
            
        try:
            result = await service.recall(node)
            # Ensure we return a MemoryOpResult
            if isinstance(result, MemoryOpResult):
                return result
            # Convert to MemoryOpResult if needed
            return MemoryOpResult(
                status=MemoryOpStatus.SUCCESS,
                reason="Recalled successfully",
                data=result if result else None
            )
        except Exception as e:
            logger.error(f"Failed to recall node: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
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
            # Ensure we return a MemoryOpResult
            if isinstance(result, MemoryOpResult):
                return result
            # Convert to MemoryOpResult if needed
            return MemoryOpResult(
                status=MemoryOpStatus.SUCCESS,
                reason="Forgotten successfully",
                data=result if result else None
            )
        except Exception as e:
            logger.error(f"Failed to forget node: {e}", exc_info=True)
            return MemoryOpResult(
                status=MemoryOpStatus.FAILED,
                reason=str(e),
                error=str(e)
            )
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process a memory message"""
        # For now, all memory operations are synchronous
        # This bus mainly exists for consistency and future async operations
        logger.warning(f"Memory operations should be synchronous, got queued message: {type(message)}")