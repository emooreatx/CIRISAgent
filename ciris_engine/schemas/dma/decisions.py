"""
DMA decision schemas for contract-driven architecture.

Typed decisions from each Decision Making Algorithm.
"""

from typing import List
from pydantic import BaseModel, Field, ConfigDict
from pydantic import Field, ConfigDict

class PDMADecision(BaseModel):
    """Decision from Principled Decision Making Algorithm."""
    action: str = Field(..., description="Recommended action")
    principles_evaluated: List[str] = Field(..., description="List of principles evaluated")
    violations_found: List[str] = Field(default_factory=list, description="Principle violations found")
    ethical_justification: str = Field(..., description="Ethical justification for the action")
    
    model_config = ConfigDict(extra = "forbid")

class CSDMADecision(BaseModel):
    """Decision from Common Sense Decision Making Algorithm."""
    action: str = Field(..., description="Recommended action")
    practical_considerations: List[str] = Field(..., description="Practical considerations evaluated")
    safety_concerns: List[str] = Field(default_factory=list, description="Safety concerns identified")
    common_sense_rating: float = Field(..., ge=0.0, le=1.0, description="Common sense rating (0.0 to 1.0)")
    
    model_config = ConfigDict(extra = "forbid")

class DSDMADecision(BaseModel):
    """Decision from Domain Specific Decision Making Algorithm."""
    action: str = Field(..., description="Recommended action")
    domain: str = Field(..., description="Domain of expertise")
    domain_expertise_applied: List[str] = Field(..., description="Domain expertise applied")
    domain_specific_risks: List[str] = Field(default_factory=list, description="Domain-specific risks identified")
    
    model_config = ConfigDict(extra = "forbid")

class ActionSelectionDecision(BaseModel):
    """Meta-decision from Action Selection DMA."""
    selected_action: str = Field(..., description="The selected action")
    pdma_weight: float = Field(..., ge=0.0, le=1.0, description="Weight given to PDMA input")
    csdma_weight: float = Field(..., ge=0.0, le=1.0, description="Weight given to CSDMA input")
    dsdma_weight: float = Field(..., ge=0.0, le=1.0, description="Weight given to DSDMA input")
    selection_reasoning: str = Field(..., description="Reasoning for the selection")
    alternative_actions: List[str] = Field(default_factory=list, description="Alternative actions considered")
    
    model_config = ConfigDict(extra = "forbid")