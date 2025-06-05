from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from enum import Enum
from .versioning import SchemaVersion

class ToolExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"

class ToolResult(BaseModel):
    """Result from tool execution."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    tool_name: str
    execution_status: ToolExecutionStatus
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
