import time
from ciris_engine.processor.state_manager import StateManager
from ciris_engine.schemas.states_v1 import AgentState
import pytest


def test_valid_transition_records_history():
    # Start in WAKEUP state to allow valid transitions
    sm = StateManager(initial_state=AgentState.WAKEUP)
    assert sm.get_state() == AgentState.WAKEUP
    assert len(sm.state_history) == 1

    # Transition to a valid state from WAKEUP
    assert sm.transition_to(AgentState.WORK)
    assert sm.get_state() == AgentState.WORK
    # history should now have two entries
    assert len(sm.state_history) == 2
    # metadata should have WORK entry
    assert AgentState.WORK in sm.state_metadata


def test_invalid_transition_does_not_change_state():
    sm = StateManager(initial_state=AgentState.WAKEUP)
    # Try an invalid transition (e.g., WAKEUP -> PLAY is not valid)
    # First check what transitions are actually valid from WAKEUP
    # Valid transitions from WAKEUP are: WORK, DREAM, SHUTDOWN
    # So let's test an actually invalid transition: WAKEUP -> PLAY
    assert not sm.transition_to(AgentState.PLAY)
    assert sm.get_state() == AgentState.WAKEUP
    # history should not record the failed transition
    assert len(sm.state_history) == 1


def test_state_duration(monkeypatch):
    # Start in WAKEUP state to have metadata
    sm = StateManager(initial_state=AgentState.WAKEUP)
    enter_time = sm.state_metadata[AgentState.WAKEUP]["entered_at"]
    past = time.time() - 5
    monkeypatch.setitem(
        sm.state_metadata[AgentState.WAKEUP],
        "entered_at",
        time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(past)),
    )
    duration = sm.get_state_duration()
    assert duration >= 5
    sm.state_metadata[AgentState.WAKEUP]["entered_at"] = enter_time


def test_shutdown_state_is_terminal():
    """Test that SHUTDOWN state is terminal except for the special WAKEUP transition."""
    sm = StateManager(initial_state=AgentState.SHUTDOWN)
    assert sm.get_state() == AgentState.SHUTDOWN
    
    # SHUTDOWN -> WAKEUP is allowed for startup
    assert sm.transition_to(AgentState.WAKEUP)
    assert sm.get_state() == AgentState.WAKEUP
    
    # Transition back to SHUTDOWN
    assert sm.transition_to(AgentState.SHUTDOWN)
    assert sm.get_state() == AgentState.SHUTDOWN
    
    # Cannot transition from SHUTDOWN to any other state (except WAKEUP)
    assert not sm.transition_to(AgentState.WORK)
    assert not sm.transition_to(AgentState.DREAM)
    assert not sm.transition_to(AgentState.PLAY)
    assert not sm.transition_to(AgentState.SOLITUDE)
    
    # State should remain SHUTDOWN
    assert sm.get_state() == AgentState.SHUTDOWN


def test_transitions_to_shutdown_are_valid():
    """Test that any state can transition TO shutdown."""
    # Test from each state
    for from_state in [AgentState.WAKEUP, AgentState.WORK, AgentState.DREAM, 
                       AgentState.PLAY, AgentState.SOLITUDE]:
        sm = StateManager(initial_state=from_state)
        assert sm.transition_to(AgentState.SHUTDOWN)
        assert sm.get_state() == AgentState.SHUTDOWN


def test_default_initial_state_is_shutdown():
    """Test that StateManager defaults to SHUTDOWN state."""
    sm = StateManager()
    assert sm.get_state() == AgentState.SHUTDOWN
