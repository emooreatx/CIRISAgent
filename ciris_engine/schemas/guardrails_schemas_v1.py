from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum

class GuardrailStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"

class GuardrailCheckResult(BaseModel):
    """Unified result from guardrail safety checks."""
    status: GuardrailStatus
    passed: GuardrailStatus
    reason: Optional[str] = None
    epistemic_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Detailed check results
    entropy_check: Optional[Dict[str, Any]] = None
    coherence_check: Optional[Dict[str, Any]] = None
    optimization_veto_check: Optional[Dict[str, Any]] = None
    epistemic_humility_check: Optional[Dict[str, Any]] = None
    
    # Metrics
    entropy_score: Optional[float] = None
    coherence_score: Optional[float] = None
    
    # Processing metadata
    check_timestamp: GuardrailStatus
    processing_time_ms: Optional[float] = None
