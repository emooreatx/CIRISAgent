import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def build_dispatch_context(
    thought, 
    task=None, 
    app_config=None, 
    startup_channel_id=None, 
    round_number=None, 
    extra_context=None
):
    """
    Build a dispatch context for thought processing.
    
    Args:
        thought: The thought object being processed
        task: Optional task associated with the thought
        app_config: Optional app configuration for determining origin service
        startup_channel_id: Optional fallback channel ID
        round_number: Optional round number for processing
        extra_context: Optional additional context to merge
    
    Returns:
        Dict containing the dispatch context
    """
    # Start with initial context from thought if available
    context = {}
    if hasattr(thought, "initial_context") and thought.initial_context:
        context = thought.initial_context.copy()
    
    # Core identifiers
    context["thought_id"] = thought.thought_id
    context["source_task_id"] = thought.source_task_id
    
    # Determine origin service
    if app_config and hasattr(app_config, "agent_mode"):
        origin_service = "CLI" if app_config.agent_mode.lower() == "cli" else "discord"
    else:
        origin_service = "discord"  # Default
    context["origin_service"] = origin_service
    
    # Add round number if provided
    if round_number is not None:
        context["round_number"] = round_number
    
    # Extract context from task
    channel_id = None
    if task and getattr(task, "context", None):
        for key in ["channel_id", "author_name", "author_id"]:
            if key in task.context:
                context[key] = task.context[key]
        channel_id = task.context.get("channel_id")
        
        # Ensure channel_id is also present in the thought context for downstream consumers
        if "channel_id" in task.context:
            if not hasattr(thought, 'context') or thought.context is None:
                thought.context = {}
            if isinstance(thought.context, dict):
                thought.context.setdefault("channel_id", task.context["channel_id"])
            else:
                if getattr(thought.context, "channel_id", None) is None:
                    thought.context = thought.context.model_copy(update={"channel_id": task.context["channel_id"]})
    
    # Handle channel_id fallback logic
    if not channel_id:
        channel_id = startup_channel_id
        if not channel_id:
            # Try to get from environment variable as a last resort
            import os
            channel_id = os.getenv("DISCORD_CHANNEL_ID")
            if not channel_id:
                logger.error(
                    f"No channel_id found for thought {thought.thought_id} and no startup_channel_id set; "
                    f"DISCORD_CHANNEL_ID environment variable not found. This may cause downstream errors."
                )
                channel_id = "CLI" if origin_service == "CLI" else "default"
    
    context["channel_id"] = str(channel_id)
    
    # Merge any extra context
    if extra_context:
        context.update(extra_context)
    
    return context