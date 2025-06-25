"""
Tool service schemas for CIRIS.

Defines tool information, parameters, and execution results.
"""
from typing import Dict, List, Optional, Union
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import Field

class ToolParameterType(str, Enum):
    """Supported tool parameter types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"

class ToolParameter(BaseModel):
    """Parameter definition for a tool."""
    name: str = Field(..., description="Parameter name")
    type: ToolParameterType = Field(..., description="Parameter type")
    description: str = Field(..., description="What the parameter does")
    required: bool = Field(..., description="Whether parameter is required")
    default: Optional[Union[str, int, float, bool, list, dict]] = Field(None, description="Default value if any")
    enum: Optional[List[Any]] = Field(None, description="Allowed values if restricted")
    min_value: Optional[Union[int, float]] = Field(None, description="Minimum value for numeric types")
    max_value: Optional[Union[int, float]] = Field(None, description="Maximum value for numeric types")
    pattern: Optional[str] = Field(None, description="Regex pattern for string validation")

class ToolRateLimits(BaseModel):
    """Rate limit configuration for a tool."""
    calls_per_minute: Optional[int] = Field(None, description="Max calls per minute")
    calls_per_hour: Optional[int] = Field(None, description="Max calls per hour")
    calls_per_day: Optional[int] = Field(None, description="Max calls per day")
    concurrent_calls: Optional[int] = Field(None, description="Max concurrent executions")

class ToolInfo(BaseModel):
    """Information about a tool."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="What the tool does")
    parameters: List[ToolParameter] = Field(..., description="Tool parameters")
    rate_limits: Optional[ToolRateLimits] = Field(None, description="Rate limits if any")
    last_used: Optional[datetime] = Field(None, description="When last used")
    total_uses: int = Field(0, description="Total number of uses")
    average_duration_ms: float = Field(0.0, description="Average execution time")
    success_rate: float = Field(1.0, description="Success rate (0-1)")
    requires_confirmation: bool = Field(False, description="Whether tool requires user confirmation")
    dangerous: bool = Field(False, description="Whether tool performs dangerous operations")

class ToolExecutionResult(BaseModel):
    """Result of tool execution."""
    tool_name: str = Field(..., description="Name of tool executed")
    success: bool = Field(..., description="Whether execution succeeded")
    result: Optional[Any] = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    duration_ms: float = Field(..., description="Execution duration in milliseconds")
    execution_id: str = Field(..., description="Unique execution ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))