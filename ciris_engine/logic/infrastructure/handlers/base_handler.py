"""
Base action handler - clean architecture with BusManager
"""

import asyncio
import logging
from typing import Any, Callable, Optional, Type, TypeVar
from abc import ABC, abstractmethod
from datetime import datetime

from ciris_engine.schemas.runtime.models import Thought
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.schemas.runtime.contexts import DispatchContext
from ciris_engine.schemas.audit.core import AuditEventType
from ciris_engine.logic.utils.channel_utils import extract_channel_id

from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.schemas.secrets.service import DecapsulationContext
from ciris_engine.logic.buses import BusManager
from ciris_engine.logic.utils.shutdown_manager import (
    request_global_shutdown
)
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from pydantic import BaseModel, ValidationError
from ciris_engine.logic import persistence
from ciris_engine.schemas.telemetry.core import ServiceCorrelation, CorrelationType, TraceContext, ServiceCorrelationStatus
from ciris_engine.schemas.persistence.core import CorrelationUpdateRequest

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)

class ActionHandlerDependencies:
    """Dependencies for action handlers - clean and simple."""
    def __init__(
        self,
        bus_manager: BusManager,
        time_service: TimeServiceProtocol,
        secrets_service: Optional[SecretsService] = None,
        shutdown_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.bus_manager = bus_manager
        self.time_service = time_service
        self.secrets_service = secrets_service
        self.shutdown_callback = shutdown_callback
        self._shutdown_requested = False

    def request_graceful_shutdown(self, reason: str = "Handler requested shutdown") -> None:
        """Request a graceful shutdown of the agent runtime."""
        if self._shutdown_requested:
            logger.debug("Shutdown already requested, ignoring duplicate request")
            return

        self._shutdown_requested = True
        logger.critical(f"GRACEFUL SHUTDOWN REQUESTED: {reason}")

        # Use the shutdown service if available
        if self.dependencies and self.dependencies.shutdown_service:
            asyncio.create_task(self.dependencies.shutdown_service.request_shutdown(reason))
        else:
            # Fallback to global function if service not available
            request_global_shutdown(reason)

        if self.shutdown_callback:
            try:
                self.shutdown_callback()
                logger.info("Local shutdown callback executed successfully")
            except Exception as e:
                logger.error(f"Error executing shutdown callback: {e}")

class BaseActionHandler(ABC):
    """Abstract base class for all action handlers."""

    def __init__(self, dependencies: ActionHandlerDependencies) -> None:
        self.dependencies = dependencies
        self.logger = logging.getLogger(self.__class__.__name__)

        # Quick access to commonly used dependencies
        self.bus_manager = dependencies.bus_manager
        self.time_service = dependencies.time_service
        
        # Track current correlation for tracing
        self._current_correlation: Optional[ServiceCorrelation] = None
        self._trace_start_time: Optional[datetime] = None

    @abstractmethod
    async def handle(
        self,
        result: ActionSelectionDMAResult,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> Optional[str]:
        """
        Handle the action and return follow-up thought ID if created.

        Args:
            result: The action selection result from DMA
            thought: The thought being processed
            dispatch_context: Context for the dispatch

        Returns:
            Optional thought ID of any follow-up thought created
        """

    async def _audit_log(
        self,
        action_type: HandlerActionType,
        dispatch_context: DispatchContext,
        outcome: str = "success"
    ) -> None:
        """Log an audit event through the audit service."""
        try:
            # Check if audit service is available
            if not hasattr(self.bus_manager, 'audit_service') or not self.bus_manager.audit_service:
                self.logger.debug("Audit service not available, skipping audit log")
                return

            # Convert to proper audit event type
            audit_event_type = AuditEventType(f"handler_action_{action_type.value}")

            # Use the audit service directly (it's not a bussed service)
            await self.bus_manager.audit_service.log_event(
                event_type=str(audit_event_type),
                event_data={
                    "handler_name": self.__class__.__name__,
                    "thought_id": dispatch_context.thought_id,
                    "task_id": dispatch_context.task_id,
                    "action": action_type.value,
                    "outcome": outcome,
                    "wa_authorized": dispatch_context.wa_authorized
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")
            # Audit failures should not break handler execution

    async def _handle_error(
        self,
        action_type: HandlerActionType,
        dispatch_context: DispatchContext,
        thought_id: str,
        error: Exception
    ) -> None:
        """Handle and log errors consistently."""
        self.logger.error(
            f"Error in {self.__class__.__name__} for {action_type.value} "
            f"on thought {thought_id}: {error}",
            exc_info=True
        )

        await self._audit_log(
            action_type,
            dispatch_context,
            outcome=f"error:{type(error).__name__}"
        )

    async def _validate_and_convert_params(
        self,
        params: Any,
        param_class: Type[T]
    ) -> T:
        """Validate and convert parameters to the expected type."""
        if isinstance(params, param_class):
            return params

        if isinstance(params, dict):
            try:
                return param_class.model_validate(params)
            except ValidationError as e:
                raise ValueError(f"Invalid parameters for {param_class.__name__}: {e}")

        # Try to convert BaseModel to dict first
        if hasattr(params, 'model_dump'):
            try:
                return param_class.model_validate(params.model_dump())
            except ValidationError as e:
                raise ValueError(f"Invalid parameters for {param_class.__name__}: {e}")

        raise TypeError(
            f"Expected {param_class.__name__} or dict, got {type(params).__name__}"
        )

    async def _decapsulate_secrets_in_params(
        self,
        result: ActionSelectionDMAResult,
        action_name: str,
        thought_id: str
    ) -> ActionSelectionDMAResult:
        """Auto-decapsulate any secrets in action parameters."""
        if not self.dependencies.secrets_service:
            return result

        try:
            # Decapsulate secrets in action parameters
            if result.action_parameters:
                # Convert parameters to dict if needed
                params_dict = result.action_parameters
                if hasattr(params_dict, 'model_dump'):
                    params_dict = params_dict.model_dump()

                decapsulated_params = await self.dependencies.secrets_service.decapsulate_secrets_in_parameters(
                    action_type=action_name,
                    action_params=params_dict,
                    context=DecapsulationContext(
                        action_type=action_name,
                        thought_id=thought_id
                    )
                )
                # Create a new result with decapsulated parameters
                return ActionSelectionDMAResult(
                    selected_action=result.selected_action,
                    action_parameters=decapsulated_params,
                    rationale=result.rationale,
                    # Optional fields
                    raw_llm_response=result.raw_llm_response,
                    reasoning=result.reasoning,
                    evaluation_time_ms=result.evaluation_time_ms,
                    resource_usage=result.resource_usage
                )
            return result
        except Exception as e:
            self.logger.error(f"Error decapsulating secrets: {e}")
            return result

    async def _get_channel_id(
        self,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> Optional[str]:
        """Extract channel ID from dispatch context or thought context."""
        # First try dispatch context
        channel_id = extract_channel_id(dispatch_context.channel_context)

        # Try thought's direct channel_id field
        if not channel_id and hasattr(thought, "channel_id") and thought.channel_id:
            channel_id = thought.channel_id
            self.logger.debug(f"Found channel_id in thought.channel_id: {channel_id}")

        # Try thought.context.channel_id
        if not channel_id and hasattr(thought, "context") and thought.context:
            if hasattr(thought.context, "channel_id") and thought.context.channel_id:
                channel_id = thought.context.channel_id
                self.logger.debug(f"Found channel_id in thought.context.channel_id: {channel_id}")

        # Fallback to thought context if needed
        if not channel_id and hasattr(thought, "context") and thought.context:
            # Try initial_task_context first
            if hasattr(thought.context, "initial_task_context"):
                initial_task_context = thought.context.initial_task_context
                if initial_task_context and hasattr(initial_task_context, "channel_context"):
                    channel_id = extract_channel_id(initial_task_context.channel_context)

            # Then try system_snapshot as fallback
            if not channel_id and hasattr(thought.context, "system_snapshot"):
                system_snapshot = thought.context.system_snapshot
                if system_snapshot and hasattr(system_snapshot, "channel_context"):
                    channel_id = extract_channel_id(system_snapshot.channel_context)

        # If still no channel_id, try to get it from the task
        if not channel_id and thought.source_task_id:
            task = persistence.get_task_by_id(thought.source_task_id)
            if task:
                if task.channel_id:
                    channel_id = task.channel_id
                    self.logger.debug(f"Found channel_id in task.channel_id: {channel_id}")
                elif task.context and task.context.channel_id:
                    channel_id = task.context.channel_id
                    self.logger.debug(f"Found channel_id in task.context.channel_id: {channel_id}")

        return channel_id
    
    def _create_trace_correlation(
        self,
        dispatch_context: DispatchContext,
        action_type: HandlerActionType
    ) -> None:
        """Create a trace correlation for handler execution."""
        self._trace_start_time = datetime.utcnow()
        
        # Create trace for handler execution
        trace_id = f"task_{dispatch_context.task_id or 'unknown'}_{dispatch_context.thought_id or 'unknown'}"
        span_id = f"{self.__class__.__name__.lower()}_{dispatch_context.thought_id or 'unknown'}"
        parent_span_id = f"thought_processor_{dispatch_context.thought_id or 'unknown'}"
        
        trace_context = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            span_name=f"{self.__class__.__name__}_handle",
            span_kind="internal",
            baggage={
                "thought_id": dispatch_context.thought_id or "",
                "task_id": dispatch_context.task_id or "",
                "handler_type": self.__class__.__name__,
                "action_type": action_type.value
            }
        )
        
        self._current_correlation = ServiceCorrelation(
            correlation_id=f"trace_{span_id}_{datetime.utcnow().timestamp()}",
            correlation_type=CorrelationType.TRACE_SPAN,
            service_type="handler",
            handler_name=self.__class__.__name__,
            action_type=action_type.value,
            created_at=self._trace_start_time,
            updated_at=self._trace_start_time,
            timestamp=self._trace_start_time,
            trace_context=trace_context,
            tags={
                "thought_id": dispatch_context.thought_id or "",
                "task_id": dispatch_context.task_id or "",
                "component_type": "handler",
                "handler_type": self.__class__.__name__,
                "trace_depth": "5"
            }
        )
        
        # Add correlation
        persistence.add_correlation(self._current_correlation, self.time_service)
    
    def _update_trace_correlation(
        self,
        success: bool,
        result_summary: str
    ) -> None:
        """Update the trace correlation with results."""
        if not self._current_correlation or not self._trace_start_time:
            return
            
        end_time = datetime.utcnow()
        update_req = CorrelationUpdateRequest(
            correlation_id=self._current_correlation.correlation_id,
            response_data={
                "success": str(success).lower(),
                "result_summary": result_summary,
                "execution_time_ms": str((end_time - self._trace_start_time).total_seconds() * 1000)
            },
            status=ServiceCorrelationStatus.COMPLETED if success else ServiceCorrelationStatus.FAILED
        )
        persistence.update_correlation(update_req, self.time_service)

    async def _send_notification(
        self,
        channel_id: str,
        content: str
    ) -> bool:
        """Send a notification using the communication bus."""
        if not isinstance(content, str):
            self.logger.error(f"Content must be a string, got {type(content)}")
            return False

        if not channel_id or not content:
            self.logger.error("Missing channel_id or content")
            return False

        try:
            # Use the communication bus
            return await self.bus_manager.communication.send_message(
                channel_id=channel_id,
                content=content,
                handler_name=self.__class__.__name__
            )
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}", exc_info=True)
            return False
