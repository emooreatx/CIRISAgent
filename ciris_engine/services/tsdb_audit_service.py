"""
TSDB Audit Service

Audit service implementation that stores audit events as correlations in the TSDB,
enabling time-series queries and unified telemetry storage.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus, CorrelationType
from ciris_engine.persistence.models.correlations import add_correlation
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry

logger = logging.getLogger(__name__)


class TSDBSignedAuditService(Service):
    """
    Audit service that stores events in TSDB as correlations.
    
    This service can be used standalone or alongside file-based audit logging.
    All audit events are stored as correlations with the AUDIT_EVENT type,
    enabling time-series queries and agent introspection.
    """
    
    def __init__(self,
                 tags: Optional[Dict[str, str]] = None,
                 retention_policy: str = "raw",
                 enable_file_backup: bool = True,
                 file_audit_service: Optional[Any] = None):
        """
        Initialize the TSDB audit service.
        
        Args:
            tags: Global tags to add to all audit correlations
            retention_policy: Retention policy for audit events
            enable_file_backup: Whether to also write to file-based audit
            file_audit_service: Optional file-based audit service for redundancy
        """
        super().__init__()
        self.tags = tags or {"source": "ciris_agent"}
        self.retention_policy = retention_policy
        self.enable_file_backup = enable_file_backup
        self.file_audit_service = file_audit_service
        
    async def start(self) -> None:
        """Start the audit service."""
        await super().start()
        
        if self.enable_file_backup and self.file_audit_service:
            await self.file_audit_service.start()
            
        logger.info("TSDB audit service started")
    
    async def stop(self) -> None:
        """Stop the audit service."""
        if self.enable_file_backup and self.file_audit_service:
            await self.file_audit_service.stop()
            
        await super().stop()
        logger.info("TSDB audit service stopped")
    
    async def log_action(
        self,
        handler_action: HandlerActionType,
        context: Dict[str, Any],
        outcome: Optional[str] = None,
    ) -> bool:
        """
        Log an action as an audit event correlation.
        
        Args:
            handler_action: The action type being audited
            context: Context dictionary with action details
            outcome: Optional outcome description
            
        Returns:
            True if successfully logged, False otherwise
        """
        try:
            entry = AuditLogEntry(
                event_id=str(uuid4()),
                event_timestamp=datetime.now(timezone.utc).isoformat(),
                event_type=handler_action.value,
                originator_id=context.get("thought_id", "unknown"),
                target_id=context.get("target_id"),
                event_summary=self._generate_summary(handler_action, context, outcome),
                event_payload=context,
                agent_profile=context.get("agent_profile"),
                round_number=context.get("round_number"),
                thought_id=context.get("thought_id"),
                task_id=context.get("task_id") or context.get("source_task_id"),
            )
            
            audit_correlation = ServiceCorrelation(
                correlation_id=entry.event_id,
                service_type="audit",
                handler_name="audit_service",
                action_type=handler_action.value,
                correlation_type=CorrelationType.AUDIT_EVENT,
                timestamp=datetime.fromisoformat(entry.event_timestamp),
                request_data={
                    "event_type": entry.event_type,
                    "originator_id": entry.originator_id,
                    "target_id": entry.target_id,
                    "event_summary": entry.event_summary,
                    "agent_profile": entry.agent_profile,
                    "round_number": entry.round_number,
                    "thought_id": entry.thought_id,
                    "task_id": entry.task_id,
                },
                response_data={"outcome": outcome} if outcome else None,
                tags={
                    **self.tags,
                    "action": handler_action.value,
                    "severity": self._get_severity(handler_action),
                    "agent_profile": entry.agent_profile or "unknown",
                },
                status=ServiceCorrelationStatus.COMPLETED,
                retention_policy=self.retention_policy
            )
            
            await self._store_audit_correlation(audit_correlation)
            
            if self.enable_file_backup and self.file_audit_service:
                await self.file_audit_service.log_action(handler_action, context, outcome)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log audit action: {e}")
            return False
    
    async def _store_audit_correlation(self, correlation: ServiceCorrelation) -> None:
        """Store audit correlation in TSDB."""
        try:
            add_correlation(correlation)
        except Exception as e:
            logger.error(f"Failed to store audit correlation in TSDB: {e}")
    
    def _generate_summary(self, action: HandlerActionType, context: Dict[str, Any], outcome: Optional[str]) -> str:
        """Generate a human-readable summary of the action."""
        summary_parts = [f"Action: {action.value}"]
        
        if "task_description" in context:
            summary_parts.append(f"Task: {context['task_description']}")
        
        if "target_id" in context:
            summary_parts.append(f"Target: {context['target_id']}")
            
        if outcome:
            summary_parts.append(f"Outcome: {outcome}")
            
        return " | ".join(summary_parts)
    
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
    
    async def query_audit_trail(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action_types: Optional[list[str]] = None,
        thought_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """
        Query audit trail from TSDB.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            action_types: Filter by specific action types
            thought_id: Filter by thought ID
            task_id: Filter by task ID
            limit: Maximum number of results
            
        Returns:
            List of audit entries
        """
        from ciris_engine.persistence.models.correlations import get_correlations_by_type_and_time
        
        try:
            # Convert times to ISO format
            start_str = start_time.isoformat() if start_time else None
            end_str = end_time.isoformat() if end_time else None
            
            # Query correlations
            correlations = get_correlations_by_type_and_time(
                correlation_type=CorrelationType.AUDIT_EVENT,
                start_time=start_str,
                end_time=end_str,
                limit=limit
            )
            
            # Filter and format results
            results = []
            for corr in correlations:
                # Check filters
                if action_types and corr.action_type not in action_types:
                    continue
                    
                if thought_id and corr.request_data and corr.request_data.get("thought_id") != thought_id:
                    continue
                    
                if task_id and corr.request_data and corr.request_data.get("task_id") != task_id:
                    continue
                
                # Format result
                result = {
                    "event_id": corr.correlation_id,
                    "timestamp": corr.timestamp.isoformat() if corr.timestamp else corr.created_at,
                    "action": corr.action_type,
                    "summary": corr.request_data.get("event_summary", "") if corr.request_data else "",
                    "thought_id": corr.request_data.get("thought_id") if corr.request_data else None,
                    "task_id": corr.request_data.get("task_id") if corr.request_data else None,
                    "outcome": corr.response_data.get("outcome") if corr.response_data else None,
                    "tags": corr.tags
                }
                results.append(result)
                
            return results
            
        except Exception as e:
            logger.error(f"Failed to query audit trail: {e}")
            return []