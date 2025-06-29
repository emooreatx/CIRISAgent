"""
State transition schemas for processor state management.
Replaces Dict[str, Any] usage in state history and transitions.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from ciris_engine.schemas.processors.states import AgentState


class StateTransitionRecord(BaseModel):
    """Record of a state transition that occurred."""
    timestamp: str = Field(description="ISO format timestamp of the transition")
    from_state: Optional[str] = Field(None, description="State before transition (None for initial state)")
    to_state: str = Field(description="State after transition")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional transition metadata")
    
    class Config:
        frozen = True  # Make immutable once created


class StateTransitionRequest(BaseModel):
    """Request to transition to a new state."""
    target_state: AgentState = Field(description="Target state to transition to")
    reason: Optional[str] = Field(None, description="Reason for the transition")
    force: bool = Field(False, description="Force transition even if conditions not met")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional transition context")


class StateTransitionResult(BaseModel):
    """Result of a state transition attempt."""
    success: bool = Field(description="Whether the transition succeeded")
    from_state: AgentState = Field(description="State before transition attempt")
    to_state: Optional[AgentState] = Field(None, description="State after transition (if successful)")
    reason: Optional[str] = Field(None, description="Reason for success or failure")
    timestamp: str = Field(description="ISO format timestamp of the attempt")
    duration_in_previous_state: Optional[float] = Field(None, description="Seconds spent in previous state")


class StateMetadata(BaseModel):
    """Metadata for a specific state."""
    entered_at: str = Field(description="ISO format timestamp when state was entered")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="State-specific metrics")
    exit_reason: Optional[str] = Field(None, description="Reason for exiting this state")
    
    def add_metric(self, key: str, value: Any) -> None:
        """Add or update a metric."""
        self.metrics[key] = value


class StateHistory(BaseModel):
    """Complete state history with typed records."""
    transitions: list[StateTransitionRecord] = Field(default_factory=list, description="Ordered list of state transitions")
    current_state: AgentState = Field(description="Current agent state")
    current_state_metadata: StateMetadata = Field(description="Metadata for current state")
    
    def add_transition(self, record: StateTransitionRecord) -> None:
        """Add a transition record to history."""
        self.transitions.append(record)
    
    def get_recent_transitions(self, limit: int = 10) -> list[StateTransitionRecord]:
        """Get the most recent transitions."""
        return self.transitions[-limit:] if self.transitions else []
    
    def get_state_duration(self, state: AgentState) -> float:
        """Calculate total time spent in a specific state across all transitions."""
        total_duration = 0.0
        
        for i, transition in enumerate(self.transitions):
            if transition.to_state == state.value:
                # Find when we left this state
                exit_time = None
                for j in range(i + 1, len(self.transitions)):
                    if self.transitions[j].from_state == state.value:
                        exit_time = self.transitions[j].timestamp
                        break
                
                # If we haven't left yet and it's the current state, use now
                if exit_time is None and self.current_state == state:
                    exit_time = datetime.now().isoformat()
                
                if exit_time:
                    enter_time = datetime.fromisoformat(transition.timestamp)
                    exit_datetime = datetime.fromisoformat(exit_time)
                    total_duration += (exit_datetime - enter_time).total_seconds()
        
        return total_duration


class StateCondition(BaseModel):
    """Condition that must be met for a state transition."""
    name: str = Field(description="Name of the condition")
    description: str = Field(description="Human-readable description")
    met: bool = Field(description="Whether the condition is currently met")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional condition details")


class StateTransitionValidation(BaseModel):
    """Validation result for a potential state transition."""
    from_state: AgentState = Field(description="Current state")
    to_state: AgentState = Field(description="Target state")
    is_valid: bool = Field(description="Whether the transition is valid")
    conditions: list[StateCondition] = Field(default_factory=list, description="Conditions checked")
    blocking_reason: Optional[str] = Field(None, description="Reason transition is blocked if invalid")