import pytest
from pydantic import ValidationError
from ciris_engine.schemas.actions.parameters import MemorizeParams, RecallParams, ForgetParams
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope

def test_memorize_params_validation():
    node = GraphNode(id="test", type=NodeType.USER, scope=GraphScope.LOCAL, attributes={})
    params = MemorizeParams(node=node)
    assert params.node.id == "test"
    assert params.scope == GraphScope.LOCAL

    node2 = GraphNode(id="t2", type=NodeType.CONCEPT, scope=GraphScope.IDENTITY, attributes={})
    params2 = MemorizeParams(node=node2)
    assert params2.scope == GraphScope.IDENTITY

def test_old_to_new_memorize_mapping():
    # Test conversion logic
    old_params = {
        "knowledge_unit_description": "user preference",
        "knowledge_data": {"preference": "dark mode"},
        "knowledge_type": "user_pref"
    }
    
    # Should map to new format
    node = GraphNode(
        id=old_params["knowledge_unit_description"],
        type=NodeType.USER,
        scope=GraphScope.LOCAL,
        attributes={"value": old_params["knowledge_data"]}
    )
    new_params = MemorizeParams(node=node)
    assert new_params.node.id == "user preference"
