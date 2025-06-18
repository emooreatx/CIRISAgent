import pytest
from ciris_engine.schemas import action_params_v1
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from pydantic import ValidationError
from ciris_engine.utils.channel_utils import create_channel_context

def test_observe_params_defaults():
    params = action_params_v1.ObserveParams()
    assert params.channel_context is None
    assert params.active is False
    assert isinstance(params.context, dict)

def test_speak_params_required():
    with pytest.raises(ValidationError):
        action_params_v1.SpeakParams()
    params = action_params_v1.SpeakParams(content="Hello", channel_context=create_channel_context("chan"))
    assert params.content == "Hello"
    assert params.channel_context is not None
    assert params.channel_context.channel_id == "chan"

def test_tool_params_defaults():
    params = action_params_v1.ToolParams(name="mytool")
    assert params.name == "mytool"
    assert isinstance(params.parameters, dict)

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
    node = GraphNode(id="foo", type=NodeType.USER, scope=GraphScope.LOCAL)
    params = action_params_v1.MemorizeParams(node=node)
    assert params.node.id == "foo"
    assert params.scope == action_params_v1.GraphScope.LOCAL

def test_Recall_params_defaults():
    node = GraphNode(id="bar", type=NodeType.USER, scope=GraphScope.LOCAL)
    params = action_params_v1.RecallParams(node=node)
    assert params.node.id == "bar"
    assert params.scope == action_params_v1.GraphScope.LOCAL

def test_forget_params():
    node = GraphNode(id="baz", type=NodeType.USER, scope=GraphScope.LOCAL)
    params = action_params_v1.ForgetParams(node=node, reason="cleanup")
    assert params.node.id == "baz"
    assert params.scope == action_params_v1.GraphScope.LOCAL
    assert params.reason == "cleanup"
