"""
Tool execution schemas for external tool integration.

Provides type-safe structures for tool invocation and results.
"""
from typing import Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import Field

class ToolExecutionStatus(str, Enum):
    """Status of tool execution."""
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
    default: Optional[Union[str, int, float, bool]] = Field(
        default=None, 
        description="Default value if not provided"
    )
    enum: Optional[List[Union[str, int]]] = Field(
        default=None, 
        description="Allowed values for enum parameters"
    )
    min_value: Optional[float] = Field(default=None, description="Minimum value for numeric parameters")
    max_value: Optional[float] = Field(default=None, description="Maximum value for numeric parameters")
    min_length: Optional[int] = Field(default=None, description="Minimum length for string parameters")
    max_length: Optional[int] = Field(default=None, description="Maximum length for string parameters")
    
    class Config:
        extra = "forbid"

class ToolExample(BaseModel):
    """Example tool invocation."""
    description: str = Field(..., description="What this example demonstrates")
    parameters: Dict[str, Union[str, int, float, bool]] = Field(..., description="Example parameters")
    expected_result: Optional[str] = Field(None, description="Expected result description")
    
    class Config:
        extra = "forbid"

class ToolDescription(BaseModel):
    """Complete description of a tool including its parameters."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Human-readable tool description")
    category: str = Field(default="general", description="Tool category (e.g., file, system, discord)")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    returns: str = Field(default="ToolResult", description="Description of return value")
    examples: Optional[List[ToolExample]] = Field(default=None, description="Example invocations")
    requires_auth: bool = Field(default=False, description="Whether tool requires authentication")
    rate_limit: Optional[int] = Field(default=None, description="Rate limit per minute")
    timeout_seconds: float = Field(default=30.0, description="Execution timeout")
    
    class Config:
        extra = "forbid"

class ToolInvocation(BaseModel):
    """Request to invoke a tool."""
    tool_name: str = Field(..., description="Name of tool to invoke")
    parameters: Dict[str, Union[str, int, float, bool, List[str], Dict[str, str]]] = Field(
        default_factory=dict, 
        description="Tool parameters with typed values"
    )
    correlation_id: Optional[str] = Field(default=None, description="Correlation ID for tracking")
    timeout_override: Optional[float] = Field(default=None, description="Override default timeout")
    
    class Config:
        extra = "forbid"

class ToolResult(BaseModel):
    """Result from tool execution."""
    tool_name: str = Field(..., description="Name of executed tool")
    execution_status: ToolExecutionStatus = Field(..., description="Execution status")
    result_data: Optional[Dict[str, str]] = Field(None, description="Result data as strings")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: Optional[float] = Field(None, description="Execution time in milliseconds")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        extra = "forbid"

class ToolRegistryEntry(BaseModel):
    """Entry in the tool registry."""
    tool_description: ToolDescription = Field(..., description="Tool description")
    adapter_id: str = Field(..., description="ID of adapter providing this tool")
    adapter_type: str = Field(..., description="Type of adapter")
    enabled: bool = Field(True, description="Whether tool is enabled")
    last_used: Optional[str] = Field(None, description="ISO timestamp of last use")
    usage_count: int = Field(0, description="Number of times used")
    
    class Config:
        extra = "forbid"

class ToolCapability(BaseModel):
    """Capability provided by a tool."""
    capability: str = Field(..., description="Capability identifier")
    description: str = Field(..., description="What this capability enables")
    required_permissions: List[str] = Field(
        default_factory=list, 
        description="Required permissions"
    )
    
    class Config:
        extra = "forbid"

__all__ = [
    "ToolExecutionStatus",
    "ToolParameterType",
    "ToolParameter",
    "ToolExample",
    "ToolDescription",
    "ToolInvocation",
    "ToolResult",
    "ToolRegistryEntry",
    "ToolCapability"
]