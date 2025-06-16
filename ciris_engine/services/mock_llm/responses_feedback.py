from typing import Optional, Any
from ciris_engine.schemas.feedback_schemas_v1 import OptimizationVetoResult, EpistemicHumilityResult

def optimization_veto(context: Optional[Any] = None) -> OptimizationVetoResult:
    """Mock OptimizationVetoResult with passing values, instructor compatible."""
    result = OptimizationVetoResult(
        decision="proceed",
        justification="Acceptable risk-benefit ratio",
        entropy_reduction_ratio=0.5,
        affected_values=["autonomy", "justice"],
        confidence=0.8
    )
    # Return structured result directly - instructor will handle it
    return result

def epistemic_humility(context: Optional[Any] = None) -> EpistemicHumilityResult:
    """Mock EpistemicHumilityResult with passing values, instructor compatible."""
    result = EpistemicHumilityResult(
        epistemic_certainty=0.7,
        identified_uncertainties=["none"],
        reflective_justification="Clear understanding of requirements",
        recommended_action="proceed"
    )
    # Return structured result directly - instructor will handle it
    return result
