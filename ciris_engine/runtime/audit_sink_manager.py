"""
Audit Sink Manager - Runtime component for managing audit event lifecycle.

This runtime component manages the audit sink, tracking consumers and
implementing cleanup policies based on time and consumer acknowledgments.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Set, List, Optional, Any
from dataclasses import dataclass, field

from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry

logger = logging.getLogger(__name__)


@dataclass
class AuditEventMetadata:
    """Metadata for tracking audit event lifecycle."""
    event_id: str
    timestamp: datetime
    consumers: Set[str] = field(default_factory=set)
    acknowledged_by: Set[str] = field(default_factory=set)
    
    @property
    def is_fully_acknowledged(self) -> bool:
        """Check if all consumers have acknowledged this event."""
        return self.consumers == self.acknowledged_by
    
    @property
    def age_seconds(self) -> float:
        """Get age of event in seconds."""
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()


class AuditSinkManager:
    """
    Runtime manager for audit sink lifecycle.
    
    Responsibilities:
    - Track audit event consumers
    - Manage consumer acknowledgments
    - Implement time-based expiry
    - Clean up acknowledged/expired events
    """
    
    def __init__(
        self,
        retention_seconds: int = 300,  # 5 minutes default
        min_consumers: int = 3,  # Minimum consumers before cleanup
        cleanup_interval_seconds: int = 60  # Run cleanup every minute
    ) -> None:
        self.retention_seconds = retention_seconds
        self.min_consumers = min_consumers
        self.cleanup_interval_seconds = cleanup_interval_seconds
        
        # Event tracking
        self._events: Dict[str, AuditEventMetadata] = {}
        self._event_data: Dict[str, AuditLogEntry] = {}
        
        # Consumer registry
        self._registered_consumers: Set[str] = set()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self) -> None:
        """Start the audit sink manager."""
        logger.info(
            f"Starting AuditSinkManager with retention={self.retention_seconds}s, "
            f"min_consumers={self.min_consumers}"
        )
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
    async def stop(self) -> None:
        """Stop the audit sink manager."""
        logger.info("Stopping AuditSinkManager")
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
                
    def register_consumer(self, consumer_id: str) -> None:
        """Register an audit consumer (e.g., audit service instance)."""
        self._registered_consumers.add(consumer_id)
        logger.info(f"Registered audit consumer: {consumer_id}")
        
    def unregister_consumer(self, consumer_id: str) -> None:
        """Unregister an audit consumer."""
        self._registered_consumers.discard(consumer_id)
        logger.info(f"Unregistered audit consumer: {consumer_id}")
        
    async def add_event(self, event: AuditLogEntry) -> None:
        """Add an audit event to the sink."""
        metadata = AuditEventMetadata(
            event_id=event.event_id,
            timestamp=datetime.now(timezone.utc),
            consumers=self._registered_consumers.copy()
        )
        
        self._events[event.event_id] = metadata
        self._event_data[event.event_id] = event
        
        logger.debug(
            f"Added audit event {event.event_id} with {len(metadata.consumers)} consumers"
        )
        
    async def acknowledge_event(self, event_id: str, consumer_id: str) -> bool:
        """Acknowledge that a consumer has processed an event."""
        if event_id not in self._events:
            logger.warning(f"Cannot acknowledge unknown event: {event_id}")
            return False
            
        metadata = self._events[event_id]
        if consumer_id not in metadata.consumers:
            logger.warning(
                f"Consumer {consumer_id} not registered for event {event_id}"
            )
            return False
            
        metadata.acknowledged_by.add(consumer_id)
        logger.debug(
            f"Event {event_id} acknowledged by {consumer_id} "
            f"({len(metadata.acknowledged_by)}/{len(metadata.consumers)})"
        )
        
        return True
        
    async def get_pending_events(
        self, 
        consumer_id: str,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Get pending events for a specific consumer."""
        pending = []
        
        for event_id, metadata in self._events.items():
            if (consumer_id in metadata.consumers and 
                consumer_id not in metadata.acknowledged_by):
                if event_id in self._event_data:
                    pending.append(self._event_data[event_id])
                    if len(pending) >= limit:
                        break
                        
        return pending
        
    async def _cleanup_loop(self) -> None:
        """Background task to clean up old/acknowledged events."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                await self._perform_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audit cleanup loop: {e}", exc_info=True)
                
    async def _perform_cleanup(self) -> None:
        """Perform cleanup of old and acknowledged events."""
        now = datetime.now(timezone.utc)
        events_to_remove = []
        
        for event_id, metadata in self._events.items():
            # Check if event is expired
            if metadata.age_seconds > self.retention_seconds:
                events_to_remove.append(event_id)
                logger.debug(f"Event {event_id} expired (age: {metadata.age_seconds}s)")
                continue
                
            # Check if event is fully acknowledged by minimum consumers
            if (metadata.is_fully_acknowledged and 
                len(metadata.acknowledged_by) >= self.min_consumers):
                events_to_remove.append(event_id)
                logger.debug(
                    f"Event {event_id} fully acknowledged by "
                    f"{len(metadata.acknowledged_by)} consumers"
                )
                
        # Remove cleaned up events
        for event_id in events_to_remove:
            self._events.pop(event_id, None)
            self._event_data.pop(event_id, None)
            
        if events_to_remove:
            logger.info(
                f"Cleaned up {len(events_to_remove)} audit events "
                f"(remaining: {len(self._events)})"
            )
            
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the audit sink."""
        total_events = len(self._events)
        fully_acknowledged = sum(
            1 for m in self._events.values() 
            if m.is_fully_acknowledged
        )
        
        age_distribution = {
            "< 1min": 0,
            "1-5min": 0,
            "> 5min": 0
        }
        
        for metadata in self._events.values():
            age = metadata.age_seconds
            if age < 60:
                age_distribution["< 1min"] += 1
            elif age < 300:
                age_distribution["1-5min"] += 1
            else:
                age_distribution["> 5min"] += 1
                
        return {
            "total_events": total_events,
            "fully_acknowledged": fully_acknowledged,
            "registered_consumers": len(self._registered_consumers),
            "age_distribution": age_distribution,
            "retention_seconds": self.retention_seconds,
            "min_consumers": self.min_consumers
        }