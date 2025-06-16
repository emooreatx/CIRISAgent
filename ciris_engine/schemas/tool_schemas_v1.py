from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
from enum import Enum
from .versioning import SchemaVersion

class ToolExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"

class ToolParameterType(str, Enum):
    """Supported parameter types for tools."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"

class ToolParameter(BaseModel):
    """Description of a single tool parameter."""
    name: str = Field(..., description="Parameter name")
    type: ToolParameterType = Field(..., description="Parameter type")
    description: str = Field(..., description="Human-readable parameter description")
    required: bool = Field(default=True, description="Whether this parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value if not provided")
    enum: Optional[List[Any]] = Field(default=None, description="Allowed values for enum parameters")
    min_value: Optional[float] = Field(default=None, description="Minimum value for numeric parameters")
    max_value: Optional[float] = Field(default=None, description="Maximum value for numeric parameters")
    min_length: Optional[int] = Field(default=None, description="Minimum length for string parameters")
    max_length: Optional[int] = Field(default=None, description="Maximum length for string parameters")

class ToolDescription(BaseModel):
    """Complete description of a tool including its parameters."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Human-readable tool description")
    category: str = Field(default="general", description="Tool category (e.g., file, system, discord)")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    returns: str = Field(default="ToolResult", description="Description of return value")
    examples: Optional[List[Dict[str, Any]]] = Field(default=None, description="Example invocations")
    requires_auth: bool = Field(default=False, description="Whether tool requires authentication")
    rate_limit: Optional[int] = Field(default=None, description="Rate limit per minute")
    timeout_seconds: Optional[float] = Field(default=30.0, description="Execution timeout")

class ToolInvocation(BaseModel):
    """Request to invoke a tool."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    tool_name: str = Field(..., description="Name of tool to invoke")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    correlation_id: Optional[str] = Field(default=None, description="Correlation ID for tracking")
    timeout_override: Optional[float] = Field(default=None, description="Override default timeout")

class ToolResult(BaseModel):
    """Result from tool execution."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    tool_name: str
    execution_status: ToolExecutionStatus
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
