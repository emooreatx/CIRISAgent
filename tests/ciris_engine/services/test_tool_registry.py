import pytest
from ciris_engine.adapters import ToolRegistry

def test_register_and_get_tool():
    from ciris_engine.schemas.tool_schemas_v1 import ToolParameterType
    
    reg = ToolRegistry()
    reg.register_tool("foo", {"a": int}, lambda x: x)
    
    # Tool registry converts Python types to ToolParameterType enums
    schema = reg.get_tool_schema("foo")
    assert schema is not None
    assert schema["a"] == ToolParameterType.INTEGER  # int -> INTEGER enum
    
    assert reg.get_handler("foo") is not None
    assert reg.validate_arguments("foo", {"a": 1})
    assert not reg.validate_arguments("bar", {"a": 1})
