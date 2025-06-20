"""
TSDB Audit Service

Audit service implementation that stores audit events as correlations in the TSDB,
enabling time-series queries and unified telemetry storage.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from uuid import uuid4

from ciris_engine.adapters.base import Service
from ciris_engine.protocols.services import AuditService
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus, CorrelationType
from ciris_engine.persistence.models.correlations import add_correlation
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry
from ciris_engine.schemas.protocol_schemas_v1 import ActionContext, AuditEntry, GuardrailCheckResult

logger = logging.getLogger(__name__)


class TSDBSignedAuditService(AuditService):
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
    
    async def log_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Log a general event.
        
        Args:
            event_type: Type of event being logged
            event_data: Event data and context
        """
        try:
            entry = AuditLogEntry(
                event_id=str(uuid4()),
                event_timestamp=datetime.now(timezone.utc).isoformat(),
                event_type=event_type,
                originator_id=event_data.get("originator_id", "system"),
                target_id=event_data.get("target_id"),
                event_summary=event_data.get("summary", f"Event: {event_type}"),
                event_payload=event_data,
                agent_template=event_data.get("agent_template"),
                round_number=event_data.get("round_number"),
                thought_id=event_data.get("thought_id"),
                task_id=event_data.get("task_id"),
            )
            
            audit_correlation = ServiceCorrelation(
                correlation_id=entry.event_id,
                service_type="audit",
                handler_name="audit_service",
                action_type=event_type,
                correlation_type=CorrelationType.AUDIT_EVENT,
                timestamp=datetime.fromisoformat(entry.event_timestamp),
                request_data={
                    "event_type": entry.event_type,
                    "originator_id": entry.originator_id,
                    "target_id": entry.target_id,
                    "event_summary": entry.event_summary,
                    "agent_template": entry.agent_template,
                    "round_number": entry.round_number,
                    "thought_id": entry.thought_id,
                    "task_id": entry.task_id,
                },
                response_data=event_data,
                tags={
                    **self.tags,
                    "event": event_type,
                    "severity": event_data.get("severity", "info"),
                    "agent_template": entry.agent_template or "unknown",
                },
                status=ServiceCorrelationStatus.COMPLETED,
                retention_policy=self.retention_policy
            )
            
            await self._store_audit_correlation(audit_correlation)
            
            if self.enable_file_backup and self.file_audit_service:
                await self.file_audit_service.log_event(event_type, event_data)
                
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
    
    async def log_action(
        self,
        handler_action: HandlerActionType,
        context: ActionContext,
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
                originator_id=context.thought_id,
                target_id=context.task_id,
                event_summary=self._generate_summary(handler_action, context, outcome),
                event_payload={"thought_id": context.thought_id, "task_id": context.task_id, "handler_name": context.handler_name, "parameters": context.parameters},
                agent_template="default",
                round_number=0,
                thought_id=context.thought_id,
                task_id=context.task_id,
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
                    "agent_template": entry.agent_template,
                    "round_number": entry.round_number,
                    "thought_id": entry.thought_id,
                    "task_id": entry.task_id,
                },
                response_data={"outcome": outcome} if outcome else None,
                tags={
                    **self.tags,
                    "action": handler_action.value,
                    "severity": self._get_severity(handler_action),
                    "agent_template": entry.agent_template or "unknown",
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
    
    def _generate_summary(self, action: HandlerActionType, context: ActionContext, outcome: Optional[str]) -> str:
        """Generate a human-readable summary of the action."""
        summary_parts = [f"Action: {action.value}"]
        
        if context.task_id:
            summary_parts.append(f"Task: {context.task_id}")
        
        if context.handler_name:
            summary_parts.append(f"Handler: {context.handler_name}")
            
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
    ) -> List[AuditEntry]:
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
                result = AuditEntry(
                    entry_id=corr.correlation_id,
                    timestamp=corr.timestamp if corr.timestamp else datetime.fromisoformat(corr.created_at) if corr.created_at else datetime.now(timezone.utc),
                    entity_id=corr.request_data.get("thought_id", "") if corr.request_data else "",
                    event_type=corr.action_type,
                    actor=corr.handler_name,
                    details={
                        "action": corr.action_type,
                        "summary": corr.request_data.get("event_summary", "") if corr.request_data else "",
                        "thought_id": corr.request_data.get("thought_id") if corr.request_data else None,
                        "task_id": corr.request_data.get("task_id") if corr.request_data else None,
                        "tags": corr.tags
                    },
                    outcome=corr.response_data.get("outcome") if corr.response_data else None
                )
                results.append(result)
                
            return results
            
        except Exception as e:
            logger.error(f"Failed to query audit trail: {e}")
            return []
    
    async def log_guardrail_event(self, guardrail_name: str, action_type: str, result: GuardrailCheckResult) -> None:
        """
        Log guardrail check events.
        
        Args:
            guardrail_name: Name of the guardrail
            action_type: Type of action being checked
            result: Guardrail check result
        """
        # Create audit event with guardrail context
        event_data = {
            "event_type": "guardrail_check",
            "guardrail_name": guardrail_name,
            "action_type": action_type,
            "result": {"allowed": result.allowed, "reason": result.reason, "risk_level": result.risk_level},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await self.log_event("guardrail_check", event_data)
    
    async def get_audit_trail(self, entity_id: str, limit: int = 100) -> List[AuditEntry]:
        """
        Get audit trail for an entity.
        
        Args:
            entity_id: Entity identifier (task_id or thought_id)
            limit: Maximum number of results
            
        Returns:
            List of audit entries
        """
        # Delegate to query_audit_trail with appropriate filters
        return await self.query_audit_trail(
            start_time=None,
            end_time=None,
            action_types=None,
            thought_id=entity_id if entity_id.startswith("thought_") else None,
            task_id=entity_id if entity_id.startswith("task_") else None,
            limit=limit
        )