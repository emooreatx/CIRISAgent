"""
Graph-based AuditService that stores all audit entries as memories in the graph.

This implements the "Graph Memory as Identity Architecture" patent by routing
all audit data through the memory system as TSDBGraphNodes.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from uuid import uuid4

from ciris_engine.protocols.services import AuditService
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.protocol_schemas_v1 import ActionContext, GuardrailCheckResult, AuditEntry
from ciris_engine.schemas.graph_schemas_v1 import TSDBGraphNode, GraphScope
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus
from ciris_engine.message_buses.memory_bus import MemoryBus

logger = logging.getLogger(__name__)


class GraphAuditService(AuditService):
    """
    AuditService that stores all audit entries as graph memories.
    
    This service implements the vision where "everything is a memory" by
    converting audit logs into TSDBGraphNodes stored in the memory graph.
    """
    
    def __init__(self, memory_bus: Optional[MemoryBus] = None) -> None:
        super().__init__()
        self._memory_bus = memory_bus
        self._service_registry: Optional[Any] = None
        # Cache for recent audit entries (for quick queries)
        self._recent_entries: List[AuditEntry] = []
        self._max_cached_entries = 1000
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry for accessing memory bus."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            # Try to get memory bus from registry
            try:
                from ciris_engine.message_buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
    
    async def log_action(
        self, 
        action_type: HandlerActionType, 
        context: ActionContext, 
        outcome: Optional[str] = None
    ) -> bool:
        """
        Log an action by storing it as a memory in the graph.
        
        This creates a TSDBGraphNode and stores it via the MemoryService,
        implementing the unified audit flow.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for audit storage")
                return False
            
            # Create audit entry
            entry = AuditEntry(
                entry_id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                entity_id=context.thought_id,
                event_type=action_type.value,
                actor=context.handler_name or "system",
                details={
                    "action_type": action_type.value,
                    "thought_id": context.thought_id,
                    "task_id": context.task_id,
                    "handler_name": context.handler_name,
                    "metadata": getattr(context, "metadata", {})
                },
                outcome=outcome
            )
            
            # Create specialized TSDB graph node for the audit entry
            node = TSDBGraphNode.create_audit_node(
                action_type=action_type.value,
                outcome=outcome or "success",
                tags={
                    "thought_id": context.thought_id,
                    "task_id": context.task_id or "",
                    "handler_name": context.handler_name or "",
                    "event_id": entry.entry_id,
                    "severity": self._get_severity(action_type)
                },
                scope=GraphScope.LOCAL,  # Audit entries are immutable, stored locally
                retention_policy="raw"
            )
            
            # Store as memory via the bus
            result = await self._memory_bus.memorize(
                node=node,
                handler_name="audit_service",
                metadata={
                    "audit_entry": entry.model_dump(),
                    "immutable": True  # Mark as compliance memory
                }
            )
            
            # Cache for quick access
            self._recent_entries.append(entry)
            if len(self._recent_entries) > self._max_cached_entries:
                self._recent_entries = self._recent_entries[-self._max_cached_entries:]
            
            return result.status == MemoryOpStatus.OK
            
        except Exception as e:
            logger.error(f"Failed to log action {action_type}: {e}")
            return False
    
    async def log_event(
        self, 
        event_type: str, 
        event_data: Dict[str, Any]
    ) -> None:
        """
        Log a general event by storing it as a memory in the graph.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for event storage")
                return
            
            # Create specialized TSDB graph node for the event
            node = TSDBGraphNode.create_audit_node(
                action_type=event_type,
                outcome="logged",
                tags={
                    **event_data.get("tags", {}),
                    "event_type": event_type,
                    "severity": event_data.get("severity", "info")
                },
                scope=GraphScope.LOCAL,
                retention_policy="raw"
            )
            
            # Add event data to node attributes
            node.attributes.update({
                "event_data": event_data,
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Store as memory via the bus
            await self._memory_bus.memorize(
                node=node,
                handler_name="audit_service",
                metadata={
                    "event": True,
                    "immutable": True
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to log event {event_type}: {e}")
    
    async def log_guardrail_event(
        self, 
        guardrail_name: str, 
        action_type: str, 
        result: GuardrailCheckResult
    ) -> None:
        """
        Log guardrail check events as memories in the graph.
        """
        try:
            event_data = {
                "guardrail_name": guardrail_name,
                "action_type": action_type,
                "allowed": result.allowed,
                "reason": result.reason,
                "risk_level": result.risk_level,
                "modifications": result.modifications,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.log_event("guardrail_check", event_data)
            
        except Exception as e:
            logger.error(f"Failed to log guardrail event: {e}")
    
    async def get_audit_trail(
        self, 
        entity_id: str, 
        limit: int = 100
    ) -> List[AuditEntry]:
        """
        Get audit trail for an entity by querying the graph memory.
        
        This uses the MemoryService's recall_timeseries capability to
        retrieve historical audit data.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for audit queries")
                return []
            
            # Quick check in cache first
            cached_results = [
                entry for entry in self._recent_entries
                if entry.entity_id == entity_id
            ]
            
            if len(cached_results) >= limit:
                return cached_results[:limit]
            
            # Query from graph memory
            timeseries_data = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=24 * 30,  # Look back 30 days
                correlation_types=["AUDIT_EVENT"],
                handler_name="audit_service"
            )
            
            # Convert to AuditEntry objects
            results: List[AuditEntry] = []
            for data in timeseries_data:
                # Filter by entity ID
                tags = data.tags or {}
                if entity_id not in [tags.get('thought_id'), tags.get('task_id')]:
                    continue
                
                # Reconstruct AuditEntry
                action_type = tags.get('action_type')
                if action_type:
                    results.append(AuditEntry(
                        entry_id=tags.get('event_id', str(uuid4())),
                        timestamp=data.timestamp,
                        entity_id=tags.get('thought_id', entity_id),
                        event_type=action_type,
                        actor=tags.get('handler_name', 'system'),
                        details={
                            "action_type": action_type,
                            "thought_id": tags.get('thought_id', ''),
                            "task_id": tags.get('task_id', ''),
                            "handler_name": tags.get('handler_name', ''),
                            "tags": tags
                        },
                        outcome=tags.get('outcome')
                    ))
            
            # Sort by timestamp descending
            results.sort(key=lambda x: x.timestamp, reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}")
            return []
    
    async def query_audit_trail(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action_types: Optional[List[str]] = None,
        thought_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """
        Query audit trail with time-series filtering from the graph.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for audit queries")
                return []
            
            # Calculate hours from time range
            hours = 24 * 30  # Default to 30 days
            if start_time and end_time:
                hours = int((end_time - start_time).total_seconds() / 3600)
            elif start_time:
                hours = int((datetime.now(timezone.utc) - start_time).total_seconds() / 3600)
            
            # Query from graph memory
            timeseries_data = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=hours,
                correlation_types=["AUDIT_EVENT"],
                handler_name="audit_service"
            )
            
            # Convert and filter results
            results: List[AuditEntry] = []
            for data in timeseries_data:
                # Time range filter
                timestamp = data.timestamp
                
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue
                
                # Action type filter
                tags = data.tags or {}
                action_type = tags.get('action_type')
                if action_types and action_type not in action_types:
                    continue
                
                # Entity filters
                if thought_id and tags.get('thought_id') != thought_id:
                    continue
                if task_id and tags.get('task_id') != task_id:
                    continue
                
                # Create AuditEntry
                if action_type:
                    results.append(AuditEntry(
                        entry_id=tags.get('event_id', str(uuid4())),
                        timestamp=timestamp,
                        entity_id=tags.get('thought_id', '') or tags.get('task_id', ''),
                        event_type=action_type,
                        actor=tags.get('handler_name', 'system'),
                        details={
                            "action_type": action_type,
                            "thought_id": tags.get('thought_id', ''),
                            "task_id": tags.get('task_id', ''),
                            "handler_name": tags.get('handler_name', ''),
                            "tags": tags
                        },
                        outcome=tags.get('outcome')
                    ))
            
            # Sort by timestamp descending
            results.sort(key=lambda x: x.timestamp, reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to query audit trail: {e}")
            return []
    
    def _get_severity(self, action: HandlerActionType) -> str:
        """Determine severity level for an action."""
        # High severity actions
        if action in [HandlerActionType.DEFER, HandlerActionType.REJECT, HandlerActionType.FORGET]:
            return "high"
        
        # Medium severity actions
        if action in [HandlerActionType.TOOL, HandlerActionType.MEMORIZE, HandlerActionType.TASK_COMPLETE]:
            return "medium"
        
        # Low severity actions
        return "low"
    
    async def start(self) -> None:
        """Start the audit service."""
        logger.info("GraphAuditService started - routing all audit entries through memory graph")
    
    async def stop(self) -> None:
        """Stop the audit service."""
        # Store a final audit entry about service shutdown
        await self.log_event("audit_service_shutdown", {
            "event": "service_stop",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cached_entries": len(self._recent_entries)
        })
        logger.info("GraphAuditService stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the audit service is healthy."""
        return self._memory_bus is not None
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "log_action", "log_event", "log_guardrail_event",
            "get_audit_trail", "query_audit_trail", "graph_storage"
        ]