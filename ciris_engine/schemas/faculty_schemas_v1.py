from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class FacultyResult(BaseModel):
    """Base class for epistemic faculty results."""
    faculty_name: str = Field(..., description="Name of the faculty that produced this result")
    evaluation_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this evaluation was performed")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in the evaluation result")

class EntropyResult(FacultyResult):
    """Result from entropy evaluation."""
    entropy: float = Field(..., ge=0.0, le=1.0, description="Entropy score (0=low information, 1=high information)")
    
class CoherenceResult(FacultyResult):
    """Result from coherence evaluation."""
    coherence: float = Field(..., ge=0.0, le=1.0, description="Coherence score (0=incoherent, 1=perfectly coherent)")
    
class EpistemicHumilityResult(FacultyResult):
    """Result from epistemic humility evaluation."""
    certainty_level: float = Field(..., ge=0.0, le=1.0, description="How certain the agent should be")
    knowledge_gaps: Optional[list[str]] = Field(default=None, description="Identified areas of uncertainty")
    should_defer: bool = Field(default=False, description="Whether the agent should defer to human wisdom")
