# Protocol-facing mock responses for ActionSelectionResult and related types
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import SpeakParams
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

def action_selection(context=None):
    """Mock ActionSelectionResult with passing values and protocol-compliant types."""
    context = context or []
    
    # Extract user speech for appropriate response
    user_speech = ""
    for item in context:
        if item.startswith("echo_user_speech:"):
            user_speech = item.split(":", 1)[1]
            break
    
    # Extract memory query for recall action
    memory_query = ""
    for item in context:
        if item.startswith("echo_memory_query:"):
            memory_query = item.split(":", 1)[1]
            break
    
    # Check for forced actions (testing)
    forced_action = None
    for item in context:
        if item.startswith("forced_action:"):
            forced_action = item.split(":", 1)[1]
            break
    
    # Check for custom rationale
    custom_rationale = None
    for item in context:
        if item.startswith("custom_rationale:"):
            custom_rationale = item.split(":", 1)[1]
            break
    
    # Determine action based on context
    if forced_action:
        action = getattr(HandlerActionType, forced_action.upper(), HandlerActionType.PONDER)
        # Create appropriate params for the forced action
        if action == HandlerActionType.SPEAK:
            params = SpeakParams(content="Forced action response", channel_id="test")
        elif action == HandlerActionType.MEMORIZE:
            from ciris_engine.schemas.action_params_v1 import MemorizeParams
            params = MemorizeParams(
                node=GraphNode(id="forced/memorize", type=NodeType.CONCEPT, scope=GraphScope.LOCAL)
            )
        elif action == HandlerActionType.RECALL:
            from ciris_engine.schemas.action_params_v1 import RecallParams
            params = RecallParams(
                node=GraphNode(id="forced/recall", type=NodeType.CONCEPT, scope=GraphScope.LOCAL)
            )
        elif action == HandlerActionType.PONDER:
            from ciris_engine.schemas.action_params_v1 import PonderParams
            params = PonderParams(questions=["Forced ponder question"])
        else:
            # Default to speak for other actions
            params = SpeakParams(content="Forced action response", channel_id="test")
        rationale = f"Forced action: {forced_action}. " + " ".join(context)
    elif user_speech:
        action = HandlerActionType.SPEAK
        params = SpeakParams(content=f"Mock response to: {user_speech}", channel_id="test")
        rationale = f"Responding to user speech: {user_speech}. " + " ".join(context)
    elif memory_query:
        action = HandlerActionType.RECALL
        from ciris_engine.schemas.action_params_v1 import RecallParams
        params = RecallParams(
            node=GraphNode(id=f"query/{memory_query}", type=NodeType.CONCEPT, scope=GraphScope.LOCAL)
        )
        rationale = f"Recalling memory for: {memory_query}. " + " ".join(context)
    else:
        # Default ponder action
        action = HandlerActionType.PONDER
        from ciris_engine.schemas.action_params_v1 import PonderParams
        params = PonderParams(questions=["What should I do next?"])
        rationale = "No specific context detected, defaulting to ponder action."
    
    # Use custom rationale if provided, otherwise use the generated rationale
    final_rationale = custom_rationale if custom_rationale else rationale
    
    result = ActionSelectionResult(
        selected_action=action,
        action_parameters=params,
        rationale=final_rationale,
        confidence=0.9
    )
    object.__setattr__(result, 'choices', [result])
    object.__setattr__(result, 'finish_reason', 'stop')
    object.__setattr__(result, '_raw_response', 'mock')
    return result
