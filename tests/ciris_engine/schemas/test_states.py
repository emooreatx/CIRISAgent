from ciris_engine.schemas.states_v1 import AgentState

def test_agent_state_enum():
    assert AgentState.WAKEUP == "wakeup"
    assert AgentState.SHUTDOWN == "shutdown"
    assert AgentState.PLAY == "play"
