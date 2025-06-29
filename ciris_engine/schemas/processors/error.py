"""
Processor error handling schemas.

Replaces Dict[str, Any] in handle_error() method with typed schemas.
"""
from enum import Enum
from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class ErrorSeverity(str, Enum):
    """Severity levels for processor errors."""
    LOW = "low"          # Can be ignored, processing continues
    MEDIUM = "medium"    # Should be logged, processing continues with caution
    HIGH = "high"        # Significant issue, may need intervention
    CRITICAL = "critical"  # Processing should stop, immediate attention needed


class ErrorContext(BaseModel):
    """Context information for processor error handling."""
    processor_name: str = Field(..., description="Name of the processor where error occurred")
    state: str = Field(..., description="Current AgentState when error occurred")
    round_number: int = Field(..., description="Processing round when error occurred")
    operation: str = Field(..., description="Operation being performed (e.g., 'process_thought', 'dispatch_action')")
    item_id: Optional[str] = Field(None, description="ID of item being processed if applicable")
    thought_content: Optional[str] = Field(None, description="Thought content if error during thought processing")
    action_type: Optional[str] = Field(None, description="Action type if error during action dispatch")
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Any additional context")


class ProcessingError(BaseModel):
    """Structured error information for processor errors."""
    error_type: str = Field(..., description="Type of error (e.g., exception class name)")
    error_message: str = Field(..., description="Human-readable error message")
    severity: ErrorSeverity = Field(..., description="Severity level of the error")
    timestamp: datetime = Field(..., description="When the error occurred")
    context: ErrorContext = Field(..., description="Context about the error")
    stack_trace: Optional[str] = Field(None, description="Stack trace if available")
    recovery_attempted: bool = Field(False, description="Whether recovery was attempted")
    recovery_successful: bool = Field(False, description="Whether recovery succeeded")
    should_continue: bool = Field(True, description="Whether processing should continue")


class ErrorHandlingResult(BaseModel):
    """Result of error handling operation."""
    handled: bool = Field(..., description="Whether error was successfully handled")
    should_continue: bool = Field(..., description="Whether processing should continue")
    recovery_action: Optional[str] = Field(None, description="Action taken to recover")
    new_state: Optional[str] = Field(None, description="New state to transition to if needed")
    error_logged: bool = Field(True, description="Whether error was logged")
    metrics_updated: bool = Field(True, description="Whether error metrics were updated")


class ProcessorConfig(BaseModel):
    """Configuration for a processor."""
    processor_name: str = Field(..., description="Name of the processor")
    supported_states: list[str] = Field(..., description="States this processor supports")
    max_retries: int = Field(3, description="Maximum retry attempts on error")
    timeout_seconds: Optional[int] = Field(None, description="Processing timeout in seconds")
    error_threshold: int = Field(10, description="Error count before processor is considered unhealthy")
    config_overrides: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Processor-specific configuration")


__all__ = [
    "ErrorSeverity",
    "ErrorContext", 
    "ProcessingError",
    "ErrorHandlingResult",
    "ProcessorConfig"
]