from typing import Optional, Any
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult

def entropy(context: Optional[Any] = None) -> EntropyResult:
    """Mock EntropyResult with passing value (entropy=0.1), instructor compatible."""
    result = EntropyResult(entropy=0.1)
    object.__setattr__(result, 'choices', [result])
    object.__setattr__(result, 'finish_reason', 'stop')
    object.__setattr__(result, '_raw_response', 'mock')
    return result

def coherence(context: Optional[Any] = None) -> CoherenceResult:
    """Mock CoherenceResult with passing value (coherence=0.9), instructor compatible."""
    result = CoherenceResult(coherence=0.9)
    object.__setattr__(result, 'choices', [result])
    object.__setattr__(result, 'finish_reason', 'stop')
    object.__setattr__(result, '_raw_response', 'mock')
    return result

