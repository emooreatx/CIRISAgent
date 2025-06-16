import logging
from typing import Any, Dict, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ciris_engine.schemas.processing_schemas_v1 import GuardrailResult

from ciris_engine.schemas.foundational_schemas_v1 import DispatchContext, HandlerActionType

logger = logging.getLogger(__name__)

def build_dispatch_context(
    thought: Any, 
    task: Optional[Any] = None, 
    app_config: Optional[Any] = None, 
    round_number: Optional[int] = None, 
    extra_context: Optional[Dict[str, Any]] = None,
    guardrail_result: Optional['GuardrailResult'] = None,
    action_type: Optional[Any] = None
) -> DispatchContext:
    """
    Build a type-safe dispatch context for thought processing.
    
    Args:
        thought: The thought object being processed
        task: Optional task associated with the thought
        app_config: Optional app configuration for determining origin service
        round_number: Optional round number for processing
        extra_context: Optional additional context to merge
        guardrail_result: Optional guardrail evaluation results
    
    Returns:
        DispatchContext object with all relevant fields populated
    """
    # Start with base context data
    context_data: Dict[str, Any] = {}
    
    # Extract initial context from thought if available
    if hasattr(thought, "initial_context") and thought.initial_context:
        if isinstance(thought.initial_context, dict):
            context_data.update(thought.initial_context)
    
    # Core identification
    thought_id = getattr(thought, "thought_id", None)
    source_task_id = getattr(thought, "source_task_id", None)
    
    # Determine origin service
    if app_config and hasattr(app_config, "agent_mode"):
        origin_service = "CLI" if app_config.agent_mode.lower() == "cli" else "discord"
    else:
        origin_service = "discord"
    
    # Extract task context
    channel_id = None
    author_id = None
    author_name = None
    task_id = None
    
    if task:
        task_id = getattr(task, "task_id", None)
        if hasattr(task, "context"):
            # Handle both dict and ThoughtContext objects
            if isinstance(task.context, dict):
                channel_id = task.context.get("channel_id")
                author_id = task.context.get("author_id")
                author_name = task.context.get("author_name")
            elif hasattr(task.context, "system_snapshot"):
                # ThoughtContext object
                if task.context.system_snapshot:
                    channel_id = task.context.system_snapshot.channel_id
                    # SystemSnapshot doesn't have user_id/user_name - these come from user_profiles
                    # For wakeup tasks, we don't have a specific user
                    author_id = None
                    author_name = None
    
    # Check extra_context for channel_id as fallback
    if channel_id is None and extra_context:
        channel_id = extra_context.get("channel_id")
    
    # Channel ID is required
    if channel_id is None:
        raise ValueError(f"No channel_id found for thought {thought_id}. Adapters must provide channel_id in task context.")
    
    # Extract additional fields from extra_context
    wa_id = None
    wa_authorized = False
    correlation_id = None
    handler_name = None
    event_summary = None
    
    if extra_context:
        wa_id = extra_context.get("wa_id")
        wa_authorized = extra_context.get("wa_authorized", False)
        correlation_id = extra_context.get("correlation_id")
        handler_name = extra_context.get("handler_name")
        event_summary = extra_context.get("event_summary")
    
    # Create the DispatchContext object with defaults for None values
    dispatch_context = DispatchContext(
        # Core identification
        channel_id=str(channel_id),
        author_id=author_id or "unknown",
        author_name=author_name or "Unknown",
        
        # Service references
        origin_service=origin_service,
        handler_name=handler_name or "unknown_handler",
        
        # Action context
        action_type=action_type or HandlerActionType.SPEAK,
        thought_id=thought_id or "",
        task_id=task_id or "",
        source_task_id=source_task_id or "",
        
        # Event details
        event_summary=event_summary or "No summary provided",
        event_timestamp=datetime.utcnow().isoformat() + "Z",
        
        # Additional context
        wa_id=wa_id,
        wa_authorized=wa_authorized,
        correlation_id=correlation_id or f"ctx_{datetime.utcnow().timestamp()}",
        round_number=round_number or 0,
        
        # Guardrail results (None for terminal actions)
        guardrail_result=guardrail_result
    )
    
    return dispatch_context