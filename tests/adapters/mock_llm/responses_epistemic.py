# Protocol-facing mock responses for epistemic faculties
from ciris_engine.schemas.conscience.core import CoherenceCheckResult, EntropyCheckResult


def entropy(context=None):
    """Mock EntropyCheckResult with passing value (entropy=0.1), instructor compatible."""
    result = EntropyCheckResult(passed=True, entropy_score=0.1, threshold=0.5, message="Entropy check passed")
    object.__setattr__(result, "choices", [result])
    object.__setattr__(result, "finish_reason", "stop")
    object.__setattr__(result, "_raw_response", "mock")
    return result


def coherence(context=None):
    """Mock CoherenceCheckResult with passing value (coherence=0.9), instructor compatible."""
    result = CoherenceCheckResult(passed=True, coherence_score=0.9, threshold=0.5, message="Coherence check passed")
    object.__setattr__(result, "choices", [result])
    object.__setattr__(result, "finish_reason", "stop")
    object.__setattr__(result, "_raw_response", "mock")
    return result


# No changes needed; values already protocol-compliant (entropy=0.1, coherence=0.9).
