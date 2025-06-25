"""
Schemas for base processor operations.

These replace all Dict[str, Any] usage in base_processor.py.
"""
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic import Field

class ProcessorMetrics(BaseModel):
    """Metrics tracked by processors."""
    start_time: Optional[datetime] = Field(None, description="When processing started")
    end_time: Optional[datetime] = Field(None, description="When processing ended")
    items_processed: int = Field(0, description="Number of items processed")
    errors: int = Field(0, description="Number of errors encountered")
    rounds_completed: int = Field(0, description="Number of processing rounds completed")
    
    # Additional metrics can be added by specific processors
    additional_metrics: dict = Field(default_factory=dict, description="Processor-specific metrics")

class ProcessingResult(BaseModel):
    """Result from a processing round."""
    round_number: int = Field(..., description="Processing round number")
    success: bool = Field(..., description="Whether processing succeeded")
    items_processed: int = Field(0, description="Items processed this round")
    errors: int = Field(0, description="Errors this round")
    state_transitions: int = Field(0, description="State transitions this round")
    metrics: ProcessorMetrics = Field(..., description="Current processor metrics")
    details: Optional[dict] = Field(None, description="Additional processing details")

class ProcessorServices(BaseModel):
    """Services available to processors."""
    discord_service: Optional[object] = Field(None, description="Discord service if available")
    memory_service: Optional[object] = Field(None, description="Memory service")
    audit_service: Optional[object] = Field(None, description="Audit service")
    telemetry_service: Optional[object] = Field(None, description="Telemetry service")
    
    class Config:
        arbitrary_types_allowed = True

class ProcessorContext(BaseModel):
    """Context for processor operations."""
    processor_name: str = Field(..., description="Name of the processor")
    current_state: str = Field(..., description="Current agent state")
    round_number: int = Field(..., description="Current round number")
    channel_context: Optional[dict] = Field(None, description="Channel context if available")
    
    
class MetricsUpdate(BaseModel):
    """Update to processor metrics."""
    items_processed: Optional[int] = Field(None, description="Items processed increment")
    errors: Optional[int] = Field(None, description="Errors increment")
    rounds_completed: Optional[int] = Field(None, description="Rounds completed increment")
    additional: dict = Field(default_factory=dict, description="Additional metric updates")