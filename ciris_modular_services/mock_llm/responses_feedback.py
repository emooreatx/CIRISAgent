from typing import Optional, Any
from ciris_engine.schemas.conscience.core import OptimizationVetoResult, EpistemicHumilityResult
from typing import Any

def optimization_veto(context: Optional[Any] = None) -> OptimizationVetoResult:
    """Mock OptimizationVetoResult with passing values, instructor compatible."""
    result = OptimizationVetoResult(
        passed=True,
        detected_optimization=False,
        confidence=0.8,
        indicators=[],
        message="No harmful optimization attempts detected"
    )
    # Return structured result directly - instructor will handle it
    return result

def epistemic_humility(context: Optional[Any] = None) -> EpistemicHumilityResult:
    """Mock EpistemicHumilityResult with passing values, instructor compatible."""
    result = EpistemicHumilityResult(
        passed=True,
        humility_score=0.7,
        overconfidence_detected=False,
        uncertainty_acknowledged=True,
        message="Appropriate epistemic humility demonstrated"
    )
    # Return structured result directly - instructor will handle it
    return result
