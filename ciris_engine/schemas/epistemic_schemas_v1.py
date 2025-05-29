from pydantic import BaseModel, Field

class EntropyResult(BaseModel):
    """Result from entropy evaluation."""
    entropy: float = Field(..., ge=0.0, le=1.0)
    
class CoherenceResult(BaseModel):
    """Result from coherence evaluation."""
    coherence: float = Field(..., ge=0.0, le=1.0)
