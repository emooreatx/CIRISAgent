"""
Type-safe initialization status schemas for CIRIS Engine.

MISSION CRITICAL: Proper tracking of initialization state.
"""
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class InitializationPhase(str, Enum):
    """Phases of the initialization process."""
    DATABASE = "database"
    MEMORY = "memory"
    IDENTITY = "identity"
    SECURITY = "security"
    SERVICES = "services"
    COMPONENTS = "components"
    ADAPTERS = "adapters"
    PROCESSOR = "processor"
    VERIFICATION = "verification"
    READY = "ready"


class InitializationStatus(BaseModel):
    """Type-safe initialization status information."""
    
    complete: bool = Field(..., description="Whether initialization is complete")
    start_time: Optional[datetime] = Field(None, description="When initialization started")
    duration_seconds: Optional[float] = Field(None, description="Duration of initialization in seconds")
    completed_steps: List[str] = Field(default_factory=list, description="List of completed initialization steps")
    phase_status: Dict[str, str] = Field(default_factory=dict, description="Status of each initialization phase")
    error: Optional[str] = Field(None, description="Error message if initialization failed")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class InitializationStep(BaseModel):
    """Definition of an initialization step."""
    
    phase: InitializationPhase = Field(..., description="Which phase this step belongs to")
    name: str = Field(..., description="Name of the initialization step")
    critical: bool = Field(True, description="Whether failure of this step is critical")
    timeout: float = Field(30.0, description="Timeout for this step in seconds")
    completed: bool = Field(False, description="Whether this step has been completed")
    error: Optional[str] = Field(None, description="Error message if step failed")
    duration_seconds: Optional[float] = Field(None, description="How long the step took to complete")