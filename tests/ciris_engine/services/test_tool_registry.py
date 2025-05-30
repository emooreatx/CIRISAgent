import pytest
from ciris_engine.adapters import ToolRegistry

def test_register_and_get_tool():
    reg = ToolRegistry()
    reg.register_tool("foo", {"a": int}, lambda x: x)
    assert reg.get_tool_schema("foo") == {"a": int}
    assert reg.get_handler("foo") is not None
    assert reg.validate_arguments("foo", {"a": 1})
    assert not reg.validate_arguments("bar", {"a": 1})
