import pytest
from ciris_engine.schemas import action_params_v1
from pydantic import ValidationError

def test_observe_params_defaults():
    params = action_params_v1.ObserveParams()
    assert params.channel_id is None
    assert params.active is False
    assert isinstance(params.context, dict)

def test_speak_params_required():
    with pytest.raises(ValidationError):
        action_params_v1.SpeakParams()
    params = action_params_v1.SpeakParams(content="Hello", channel_id="chan")
    assert params.content == "Hello"
    assert params.channel_id == "chan"

def test_tool_params_defaults():
    params = action_params_v1.ToolParams(name="mytool")
    assert params.name == "mytool"
    assert isinstance(params.args, dict)

def test_ponder_params():
    params = action_params_v1.PonderParams(questions=["Q1"])
    assert params.questions == ["Q1"]

def test_reject_params():
    params = action_params_v1.RejectParams(reason="bad idea")
    assert params.reason == "bad idea"

def test_defer_params_defaults():
    params = action_params_v1.DeferParams(reason="wait")
    assert params.reason == "wait"
    assert isinstance(params.context, dict)

def test_memorize_params():
    params = action_params_v1.MemorizeParams(key="foo", value=123)
    assert params.key == "foo"
    assert params.value == 123
    assert params.scope == "local"

def test_remember_params_defaults():
    params = action_params_v1.RememberParams(query="bar")
    assert params.query == "bar"
    assert params.scope == "local"

def test_forget_params():
    params = action_params_v1.ForgetParams(key="baz", reason="cleanup")
    assert params.key == "baz"
    assert params.scope == "local"
    assert params.reason == "cleanup"
