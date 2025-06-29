"""
State-specific processing results for each AgentState.

These replace Dict[str, Any] returns from processors with type-safe schemas.
Each state has its own result type with state-specific fields.
"""
from typing import Union
from pydantic import BaseModel, Field


class WakeupResult(BaseModel):
    """Result from WAKEUP state processing."""
    thoughts_processed: int = Field(0)
    wakeup_complete: bool = Field(False)
    errors: int = Field(0)
    duration_seconds: float = Field(...)


class WorkResult(BaseModel):
    """Result from WORK state processing."""
    tasks_processed: int = Field(0)
    thoughts_processed: int = Field(0)
    errors: int = Field(0)
    duration_seconds: float = Field(...)


class PlayResult(BaseModel):
    """Result from PLAY state processing."""
    thoughts_processed: int = Field(0)
    errors: int = Field(0)
    duration_seconds: float = Field(...)


class SolitudeResult(BaseModel):
    """Result from SOLITUDE state processing."""
    thoughts_processed: int = Field(0)
    errors: int = Field(0)
    duration_seconds: float = Field(...)


class DreamResult(BaseModel):
    """Result from DREAM state processing."""
    thoughts_processed: int = Field(0)
    errors: int = Field(0)
    duration_seconds: float = Field(...)


class ShutdownResult(BaseModel):
    """Result from SHUTDOWN state processing."""
    tasks_cleaned: int = Field(0)
    shutdown_ready: bool = Field(False)
    errors: int = Field(0)
    duration_seconds: float = Field(...)


# Discriminated union of all possible results
ProcessingResult = Union[
    WakeupResult,
    WorkResult,
    PlayResult,
    SolitudeResult,
    DreamResult,
    ShutdownResult
]


__all__ = [
    "WakeupResult",
    "WorkResult",
    "PlayResult",
    "SolitudeResult",
    "DreamResult",
    "ShutdownResult",
    "ProcessingResult"
]
