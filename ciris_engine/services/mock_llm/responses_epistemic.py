from typing import Optional, Any
from ciris_engine.schemas.faculty_schemas_v1 import EntropyResult, CoherenceResult

def entropy(context: Optional[Any] = None) -> EntropyResult:
    """Mock EntropyResult with passing value (entropy=0.1), instructor compatible."""
    result = EntropyResult(faculty_name="entropy", entropy=0.1)
    # Return structured result directly - instructor will handle it
    return result

def coherence(context: Optional[Any] = None) -> CoherenceResult:
    """Mock CoherenceResult with passing value (coherence=0.9), instructor compatible."""
    result = CoherenceResult(faculty_name="coherence", coherence=0.9)
    # Return structured result directly - instructor will handle it
    return result

