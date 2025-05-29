from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from enum import Enum
from .foundational_schemas_v1 import CIRISSchemaVersion

class ToolExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"

class ToolResult(BaseModel):
    """Result from tool execution."""
    schema_version: CIRISSchemaVersion = Field(default=CIRISSchemaVersion.V1_0_BETA)
    tool_name: str
    execution_status: ToolExecutionStatus
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
