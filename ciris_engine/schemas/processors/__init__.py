"""Package initialization."""

from .core import (
    DMAResults,
    ConscienceApplicationResult,
    ProcessedThoughtResult,
    ThoughtProcessingMetrics,
    ProcessingError
)

from .error import (
    ErrorSeverity,
    ErrorContext,
    ProcessingError as ProcessorError,
    ErrorHandlingResult,
    ProcessorConfig
)

__all__ = [
    "DMAResults",
    "ConscienceApplicationResult",
    "ProcessedThoughtResult",
    "ThoughtProcessingMetrics",
    "ProcessingError",
    # Error handling schemas
    "ErrorSeverity",
    "ErrorContext",
    "ProcessorError",
    "ErrorHandlingResult",
    "ProcessorConfig"
]
