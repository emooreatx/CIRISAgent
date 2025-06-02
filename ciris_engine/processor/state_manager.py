"""
State management for the CIRISAgent processor.
Handles transitions between WAKEUP, DREAM, PLAY, WORK, SOLITUDE, and SHUTDOWN states.
"""
import logging
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from ciris_engine.schemas.states import AgentState
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus

logger = logging.getLogger(__name__)


class StateTransition:
    """Represents a state transition with validation rules."""
    
    def __init__(self, from_state: AgentState, to_state: AgentState, 
                 condition_fn=None, on_transition_fn=None):
        self.from_state = from_state
        self.to_state = to_state
        self.condition_fn = condition_fn  # Optional validation function
        self.on_transition_fn = on_transition_fn  # Optional transition handler


class StateManager:
    """Manages agent state transitions and state-specific behaviors."""
    
    # Valid state transitions
    VALID_TRANSITIONS = [
        # Allow SHUTDOWN <-> any state
        StateTransition(AgentState.SHUTDOWN, AgentState.WAKEUP),
        StateTransition(AgentState.SHUTDOWN, AgentState.WORK),
        StateTransition(AgentState.SHUTDOWN, AgentState.DREAM),
        StateTransition(AgentState.SHUTDOWN, AgentState.PLAY),
        StateTransition(AgentState.SHUTDOWN, AgentState.SOLITUDE),
        # Allow any state to SHUTDOWN
        StateTransition(AgentState.WAKEUP, AgentState.SHUTDOWN),
        StateTransition(AgentState.WORK, AgentState.SHUTDOWN),
        StateTransition(AgentState.DREAM, AgentState.SHUTDOWN),
        StateTransition(AgentState.PLAY, AgentState.SHUTDOWN),
        StateTransition(AgentState.SOLITUDE, AgentState.SHUTDOWN),
        # Original transitions
        StateTransition(AgentState.WAKEUP, AgentState.WORK),
        StateTransition(AgentState.WAKEUP, AgentState.DREAM),
        StateTransition(AgentState.WORK, AgentState.DREAM),
        StateTransition(AgentState.WORK, AgentState.PLAY),
        StateTransition(AgentState.WORK, AgentState.SOLITUDE),
        StateTransition(AgentState.DREAM, AgentState.WORK),
        StateTransition(AgentState.PLAY, AgentState.WORK),
        StateTransition(AgentState.PLAY, AgentState.SOLITUDE),
        StateTransition(AgentState.SOLITUDE, AgentState.WORK),
    ]
    
    def __init__(self, initial_state: AgentState = AgentState.SHUTDOWN):
        self.current_state = initial_state
        self.state_history = []
        self.state_metadata: Dict[AgentState, Dict[str, Any]] = {}
        self._transition_map = self._build_transition_map()
        
        # Record initial state
        self._record_state_change(initial_state, None)
    
    def _build_transition_map(self) -> Dict[AgentState, Dict[AgentState, StateTransition]]:
        """Build a map for quick transition lookups."""
        transition_map = {}
        for transition in self.VALID_TRANSITIONS:
            if transition.from_state not in transition_map:
                transition_map[transition.from_state] = {}
            transition_map[transition.from_state][transition.to_state] = transition
        return transition_map
    
    def _record_state_change(self, new_state: AgentState, old_state: Optional[AgentState]):
        """Record state change in history."""
        self.state_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_state": old_state.value if old_state else None,
            "to_state": new_state.value,
        })
    
    def can_transition_to(self, target_state: AgentState) -> bool:
        """Check if transition to target state is valid."""
        if self.current_state not in self._transition_map:
            return False
        
        if target_state not in self._transition_map[self.current_state]:
            return False
        
        transition = self._transition_map[self.current_state][target_state]
        
        # Check condition function if present
        if transition.condition_fn and not transition.condition_fn(self):
            return False
        
        return True
    
    def transition_to(self, target_state: AgentState) -> bool:
        """
        Attempt to transition to a new state.
        Returns True if successful, False otherwise.
        """
        if not self.can_transition_to(target_state):
            logger.warning(
                f"Invalid state transition attempted: {self.current_state.value} -> {target_state.value}"
            )
            return False
        
        old_state = self.current_state
        transition = self._transition_map[old_state][target_state]
        
        # Execute transition handler if present
        if transition.on_transition_fn:
            try:
                transition.on_transition_fn(self, old_state, target_state)
            except Exception as e:
                logger.error(
                    f"Error in transition handler for {old_state.value} -> {target_state.value}: {e}"
                )
                return False
        
        # Update state
        self.current_state = target_state
        self._record_state_change(target_state, old_state)
        
        logger.info(f"State transition: {old_state.value} -> {target_state.value}")
        print(f"[STATE] Transition: {old_state.value} -> {target_state.value}")  # Print to console
        
        # Initialize metadata for new state if needed
        if target_state not in self.state_metadata:
            self.state_metadata[target_state] = {
                "entered_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {}
            }
        
        return True
    
    def get_state(self) -> AgentState:
        """Get current state."""
        return self.current_state
    
    def get_state_metadata(self) -> Dict[str, Any]:
        """Get metadata for current state."""
        return self.state_metadata.get(self.current_state, {})
    
    def update_state_metadata(self, key: str, value: Any):
        """Update metadata for current state."""
        if self.current_state not in self.state_metadata:
            self.state_metadata[self.current_state] = {}
        self.state_metadata[self.current_state][key] = value
    
    def get_state_duration(self) -> float:
        """Get duration in seconds for current state."""
        metadata = self.get_state_metadata()
        if "entered_at" in metadata:
            entered_at = datetime.fromisoformat(metadata["entered_at"])
            return (datetime.now(timezone.utc) - entered_at).total_seconds()
        return 0.0
    
    def should_auto_transition(self) -> Optional[AgentState]:
        """
        Check if an automatic state transition should occur.
        Returns the target state if a transition should happen, None otherwise.
        """
        if self.current_state == AgentState.WAKEUP:
            # After successful wakeup, transition to WORK
            if self.get_state_metadata().get("wakeup_complete", False):
                return AgentState.WORK
        
        # All other auto-transitions are removed as per the new requirements.
        # For example, the transition from WORK to DREAM based on idle time,
        # and from DREAM to WORK based on duration, are no longer automatic.
        
        return None