# Protocol-facing mock responses for feedback/guardrail types
from ciris_engine.schemas.feedback_schemas_v1 import OptimizationVetoResult, EpistemicHumilityResult, FeedbackType

def optimization_veto(context=None):
    """Mock OptimizationVetoResult with passing values, instructor compatible."""
    result = OptimizationVetoResult(
        decision=FeedbackType.DECISION_OVERRIDE,
        justification=FeedbackType.POLICY_CLARIFICATION,
        entropy_reduction_ratio=FeedbackType.SYSTEM_DIRECTIVE,
        affected_values=["autonomy", "justice"],
        confidence=FeedbackType.SYSTEM_DIRECTIVE
    )
    object.__setattr__(result, 'choices', [result])
    object.__setattr__(result, 'finish_reason', 'stop')
    object.__setattr__(result, '_raw_response', 'mock')
    return result

def epistemic_humility(context=None):
    """Mock EpistemicHumilityResult with passing values, instructor compatible."""
    result = EpistemicHumilityResult(
        epistemic_certainty=FeedbackType.POLICY_CLARIFICATION,
        identified_uncertainties=["none"],
        reflective_justification=FeedbackType.POLICY_CLARIFICATION,
        recommended_action=FeedbackType.SYSTEM_DIRECTIVE
    )
    object.__setattr__(result, 'choices', [result])
    object.__setattr__(result, 'finish_reason', 'stop')
    object.__setattr__(result, '_raw_response', 'mock')
    return result
