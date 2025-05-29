import pytest
from pydantic import ValidationError
from ciris_engine.schemas.action_params_v1 import MemorizeParams, RememberParams, ForgetParams
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

def test_memorize_params_validation():
    # Valid params
    params = MemorizeParams(key="test", value="data", scope="local")
    assert params.key == "test"
    
    # Test scope enum
    params = MemorizeParams(key="test", value="data", scope="identity")
    assert params.scope == "identity"
    
    # Invalid scope should fail
    with pytest.raises(ValidationError):
        MemorizeParams(key="test", value="data", scope="invalid")

def test_old_to_new_memorize_mapping():
    # Test conversion logic
    old_params = {
        "knowledge_unit_description": "user preference",
        "knowledge_data": {"preference": "dark mode"},
        "knowledge_type": "user_pref"
    }
    
    # Should map to new format
    new_params = MemorizeParams(
        key=old_params["knowledge_unit_description"],
        value=old_params["knowledge_data"],
        scope="local"
    )
    assert new_params.key == "user preference"
