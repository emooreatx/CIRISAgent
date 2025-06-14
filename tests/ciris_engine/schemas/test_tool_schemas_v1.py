from ciris_engine.schemas.tool_schemas_v1 import ToolExecutionStatus, ToolResult
from ciris_engine.schemas.foundational_schemas_v1 import SchemaVersion

def test_tool_execution_status_enum():
    assert ToolExecutionStatus.SUCCESS == "success"
    assert ToolExecutionStatus.UNAUTHORIZED == "unauthorized"  # type: ignore[unreachable]

def test_tool_result_minimal():
    res = ToolResult(tool_name="foo", execution_status=ToolExecutionStatus.SUCCESS)
    assert res.tool_name == "foo"
    assert res.execution_status == ToolExecutionStatus.SUCCESS
    assert res.schema_version == SchemaVersion.V1_0
    assert res.result_data is None
    assert isinstance(res.metadata, dict)
