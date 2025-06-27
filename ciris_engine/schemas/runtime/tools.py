"""
Tool protocol schemas.

Type-safe schemas for tool service operations.
"""
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict
from pydantic import Field, ConfigDict

class ToolParameterSchema(BaseModel):
    """Schema for a tool parameter."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, integer, etc.)")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(True, description="Whether parameter is required")
    default: Optional[Union[str, int, float, bool]] = Field(None, description="Default value if not provided")
    enum: Optional[List[Union[str, int]]] = Field(None, description="Valid values for enum parameters")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    
    model_config = ConfigDict(extra = "forbid")

class ToolInfo(BaseModel):
    """Complete information about a tool including its source."""
    tool_name: str = Field(..., description="Name of the tool")
    display_name: str = Field(..., description="Human-friendly display name")
    description: str = Field(..., description="What the tool does")
    category: str = Field(..., description="Tool category")
    
    # Adapter identification
    adapter_id: str = Field(..., description="ID of the adapter providing this tool")
    adapter_type: str = Field(..., description="Type of adapter (discord, cli, etc.)")
    adapter_instance_name: Optional[str] = Field(None, description="Human-friendly adapter instance name")
    
    # Schema information
    parameters: List[ToolParameterSchema] = Field(default_factory=list, description="Tool parameters")
    returns_schema: Optional[Dict[str, str]] = Field(None, description="Schema of return value")
    
    # Usage information
    examples: Optional[List[Dict[str, str]]] = Field(None, description="Example invocations")
    requires_auth: bool = Field(False, description="Whether tool requires authentication")
    rate_limit: Optional[int] = Field(None, description="Rate limit per minute")
    timeout_seconds: float = Field(30.0, description="Default timeout")
    
    # Availability
    enabled: bool = Field(True, description="Whether tool is currently enabled")
    health_status: Optional[str] = Field(None, description="Current health status")
    
    model_config = ConfigDict(extra = "forbid")

class ToolExecutionRequest(BaseModel):
    """Request to execute a tool."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    adapter_id: Optional[str] = Field(None, description="Specific adapter to use (for disambiguation)")
    parameters: Dict[str, Union[str, int, float, bool, List[str], Dict[str, str]]] = Field(
        default_factory=dict, 
        description="Tool parameters with typed values"
    )
    timeout: Optional[float] = Field(None, description="Execution timeout in seconds")
    correlation_id: Optional[str] = Field(None, description="For tracking async execution")
    
    model_config = ConfigDict(extra = "forbid")

class ToolExecutionResult(BaseModel):
    """Result from tool execution."""
    success: bool = Field(..., description="Whether execution succeeded")
    result: Optional[str] = Field(None, description="Tool execution result")
    result_data: Optional[Dict[str, str]] = Field(None, description="Structured result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time: float = Field(..., description="Execution time in seconds")
    output: Optional[str] = Field(None, description="Tool output/logs")
    adapter_id: str = Field(..., description="ID of adapter that executed the tool")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional metadata")
    
    model_config = ConfigDict(extra = "forbid")

__all__ = [
    "ToolParameterSchema",
    "ToolInfo",
    "ToolExecutionRequest",
    "ToolExecutionResult"
]