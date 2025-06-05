# Protocol-facing mock responses for ActionSelectionResult and related types
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import SpeakParams
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

def action_selection(context=None):
    """Mock ActionSelectionResult with passing values and protocol-compliant types."""
    params = SpeakParams(content="Hello, world!", channel_id="test")
    rationale = "Test rationale string"
    result = ActionSelectionResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters=params,
        rationale=rationale,
        confidence=0.9
    )
    object.__setattr__(result, 'choices', [result])
    object.__setattr__(result, 'finish_reason', 'stop')
    object.__setattr__(result, '_raw_response', 'mock')
    return result
