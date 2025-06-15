import logging
from typing import Any, Dict, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ciris_engine.schemas.processing_schemas_v1 import GuardrailResult

from ciris_engine.schemas.foundational_schemas_v1 import DispatchContext

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
        if hasattr(task, "context") and isinstance(task.context, dict):
            channel_id = task.context.get("channel_id")
            author_id = task.context.get("author_id")
            author_name = task.context.get("author_name")
            
            # Update thought context with channel_id if needed
            if channel_id and "channel_id" in task.context:
                if not hasattr(thought, 'context') or thought.context is None:
                    thought.context = {}
                if isinstance(thought.context, dict):
                    thought.context.setdefault("channel_id", channel_id)
                else:
                    if getattr(thought.context, "channel_id", None) is None:
                        thought.context = thought.context.model_copy(update={"channel_id": channel_id})
    
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
    
    # Create the DispatchContext object
    dispatch_context = DispatchContext(
        # Core identification
        channel_id=str(channel_id),
        author_id=author_id,
        author_name=author_name,
        
        # Service references
        origin_service=origin_service,
        handler_name=handler_name,
        
        # Action context
        action_type=action_type,
        thought_id=thought_id,
        task_id=task_id,
        source_task_id=source_task_id,
        
        # Event details
        event_summary=event_summary,
        event_timestamp=datetime.utcnow().isoformat() + "Z",
        
        # Additional context
        wa_id=wa_id,
        wa_authorized=wa_authorized,
        correlation_id=correlation_id,
        round_number=round_number,
        
        # Guardrail results (None for terminal actions)
        guardrail_result=guardrail_result
    )
    
    return dispatch_context