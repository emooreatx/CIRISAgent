from pydantic import BaseModel, Field


class FacultyResult(BaseModel):
    """Base class for epistemic faculty results."""
    pass

class EntropyResult(FacultyResult):
    """Result from entropy evaluation."""
    entropy: float = Field(..., ge=0.0, le=1.0)
    
class CoherenceResult(FacultyResult):
    """Result from coherence evaluation."""
    coherence: float = Field(..., ge=0.0, le=1.0)
