import time
from ciris_engine.processor.state_manager import StateManager
from ciris_engine.schemas.states import AgentState


def test_valid_transition_records_history():
    sm = StateManager(initial_state=AgentState.SHUTDOWN)
    assert sm.get_state() == AgentState.SHUTDOWN
    assert len(sm.state_history) == 1

    assert sm.transition_to(AgentState.WAKEUP)
    assert sm.get_state() == AgentState.WAKEUP
    # history should now have two entries
    assert len(sm.state_history) == 2
    # metadata should have WAKEUP entry
    assert AgentState.WAKEUP in sm.state_metadata


def test_invalid_transition_does_not_change_state():
    sm = StateManager(initial_state=AgentState.WAKEUP)
    # WAKEUP -> SHUTDOWN is invalid
    assert not sm.transition_to(AgentState.SHUTDOWN)
    assert sm.get_state() == AgentState.WAKEUP
    # history size remains 1
    assert len(sm.state_history) == 1


def test_state_duration(monkeypatch):
    sm = StateManager(initial_state=AgentState.SHUTDOWN)
    sm.transition_to(AgentState.WAKEUP)
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
