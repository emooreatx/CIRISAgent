"""
Tool Discovery endpoints for CIRIS API v1.

Tool information for understanding agent capabilities.
Tools are executed by the agent during its reasoning process, not directly via API.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.adapters.tools import ToolInfo, ToolParameterSchema
from ciris_engine.api.dependencies.auth import require_observer, AuthContext

router = APIRouter(prefix="/tools", tags=["tools"])

# Response schemas

class ToolSummary(BaseModel):
    """Summary information about a tool."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Brief description of what the tool does")
    category: str = Field(..., description="Tool category")
    cost: float = Field(..., description="Cost to execute the tool")

class ToolDetail(BaseModel):
    """Detailed information about a tool."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="What the tool does")
    category: str = Field(..., description="Tool category")
    cost: float = Field(..., description="Cost to execute the tool")
    when_to_use: Optional[str] = Field(None, description="Guidance on when to use the tool")
    parameters: ToolParameterSchema = Field(..., description="Tool parameters schema")
    examples: Optional[List[Dict[str, Any]]] = Field(None, description="Example usage")

class ToolCategory(BaseModel):
    """Tool category information."""
    name: str = Field(..., description="Category name")
    description: str = Field(..., description="Category description")
    tool_count: int = Field(..., description="Number of tools in category")
    tools: List[str] = Field(..., description="Tool names in this category")

class ToolUsageStats(BaseModel):
    """Tool usage statistics."""
    tool_name: str = Field(..., description="Tool name")
    total_calls: int = Field(..., description="Total number of calls")
    success_count: int = Field(..., description="Number of successful executions")
    failure_count: int = Field(..., description="Number of failed executions")
    average_duration_ms: float = Field(..., description="Average execution time in milliseconds")
    last_used: Optional[datetime] = Field(None, description="Last time the tool was used")

class ToolsOverview(BaseModel):
    """Overview of all available tools."""
    total_tools: int = Field(..., description="Total number of available tools")
    categories: List[str] = Field(..., description="Available categories")
    tools: List[ToolSummary] = Field(..., description="List of all tools")

# Endpoints

@router.get("", response_model=SuccessResponse[ToolsOverview])
async def list_tools(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    auth: AuthContext = Depends(require_observer)
):
    """
    List available tools.
    
    Returns all tools the agent can use during its reasoning process.
    Tools are provided by the current adapter (API, CLI, Discord).
    """
    # Get tool service from adapter
    tool_service = getattr(request.app.state, 'tool_service', None)
    if not tool_service:
        # No tools available - return empty list
        return SuccessResponse(data=ToolsOverview(
            total_tools=0,
            categories=[],
            tools=[]
        ))
    
    try:
        # Get all tools
        tools: List[ToolInfo] = []
        if hasattr(tool_service, 'get_tool_info'):
            # If service provides detailed info
            tool_names = await tool_service.list_tools()
            for name in tool_names:
                try:
                    info = await tool_service.get_tool_info(name)
                    tools.append(info)
                except:
                    # Fallback if info not available
                    tools.append(ToolInfo(
                        name=name,
                        description=f"Tool: {name}",
                        parameters=ToolParameterSchema(
                            type="object",
                            properties={},
                            required=[]
                        ),
                        category="general",
                        cost=0.0
                    ))
        else:
            # Basic service - just get names
            tool_names = await tool_service.list_tools()
            tools = [
                ToolInfo(
                    name=name,
                    description=f"Tool: {name}",
                    parameters=ToolParameterSchema(
                        type="object",
                        properties={},
                        required=[]
                    ),
                    category="general",
                    cost=0.0
                )
                for name in tool_names
            ]
        
        # Filter by category if requested
        if category:
            tools = [t for t in tools if t.category.lower() == category.lower()]
        
        # Extract categories
        categories = list(set(t.category for t in tools))
        categories.sort()
        
        # Create summaries
        tool_summaries = [
            ToolSummary(
                name=t.name,
                description=t.description,
                category=t.category,
                cost=t.cost
            )
            for t in tools
        ]
        
        overview = ToolsOverview(
            total_tools=len(tools),
            categories=categories,
            tools=tool_summaries
        )
        
        return SuccessResponse(data=overview)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing tools: {str(e)}")

@router.get("/categories", response_model=SuccessResponse[List[ToolCategory]])
async def get_tool_categories(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get tool categories.
    
    Returns all available tool categories with their tools.
    """
    # Get tool service
    tool_service = getattr(request.app.state, 'tool_service', None)
    if not tool_service:
        return SuccessResponse(data=[])
    
    try:
        # Get all tools
        tools: List[ToolInfo] = []
        if hasattr(tool_service, 'get_tool_info'):
            tool_names = await tool_service.list_tools()
            for name in tool_names:
                try:
                    info = await tool_service.get_tool_info(name)
                    tools.append(info)
                except:
                    tools.append(ToolInfo(
                        name=name,
                        description=f"Tool: {name}",
                        parameters=ToolParameterSchema(
                            type="object",
                            properties={},
                            required=[]
                        ),
                        category="general",
                        cost=0.0
                    ))
        else:
            tool_names = await tool_service.list_tools()
            tools = [
                ToolInfo(
                    name=name,
                    description=f"Tool: {name}",
                    parameters=ToolParameterSchema(
                        type="object",
                        properties={},
                        required=[]
                    ),
                    category="general"
                )
                for name in tool_names
            ]
        
        # Group by category
        categories_dict: Dict[str, List[str]] = {}
        category_descriptions = {
            "general": "General purpose tools",
            "system": "System management tools",
            "communication": "Communication and messaging tools",
            "analysis": "Data analysis and processing tools",
            "integration": "External service integration tools"
        }
        
        for tool in tools:
            if tool.category not in categories_dict:
                categories_dict[tool.category] = []
            categories_dict[tool.category].append(tool.name)
        
        # Create category objects
        categories = []
        for cat_name, tool_names in sorted(categories_dict.items()):
            categories.append(ToolCategory(
                name=cat_name,
                description=category_descriptions.get(cat_name, f"{cat_name.title()} tools"),
                tool_count=len(tool_names),
                tools=sorted(tool_names)
            ))
        
        return SuccessResponse(data=categories)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting categories: {str(e)}")

@router.get("/usage", response_model=SuccessResponse[List[ToolUsageStats]])
async def get_tool_usage(
    request: Request,
    tool_name: Optional[str] = Query(None, description="Get stats for specific tool"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get tool usage statistics.
    
    Returns usage statistics for tools including call counts and performance metrics.
    """
    # Get telemetry service to query usage
    telemetry_service = getattr(request.app.state, 'telemetry_service', None)
    if not telemetry_service:
        # Return empty stats if no telemetry
        return SuccessResponse(data=[])
    
    try:
        # Query tool usage metrics from telemetry
        # This is a simplified implementation - real implementation would
        # query actual telemetry data from the graph
        
        tool_service = getattr(request.app.state, 'tool_service', None)
        if not tool_service:
            return SuccessResponse(data=[])
        
        tools = await tool_service.list_tools()
        
        # Filter by tool name if specified
        if tool_name:
            if tool_name not in tools:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
            tools = [tool_name]
        
        # Create mock usage stats (in real implementation, query from telemetry)
        stats = []
        for name in tools:
            stats.append(ToolUsageStats(
                tool_name=name,
                total_calls=0,  # Would come from telemetry
                success_count=0,
                failure_count=0,
                average_duration_ms=0.0,
                last_used=None
            ))
        
        return SuccessResponse(data=stats)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting usage stats: {str(e)}")

@router.get("/{name}", response_model=SuccessResponse[ToolDetail])
async def get_tool_details(
    request: Request,
    name: str,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get tool details.
    
    Returns detailed information about a specific tool including its schema.
    """
    # Get tool service
    tool_service = getattr(request.app.state, 'tool_service', None)
    if not tool_service:
        raise HTTPException(status_code=404, detail="Tool service not available")
    
    try:
        # Check if tool exists
        tools = await tool_service.list_tools()
        if name not in tools:
            raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
        
        # Get detailed info if available
        if hasattr(tool_service, 'get_tool_info'):
            info = await tool_service.get_tool_info(name)
            detail = ToolDetail(
                name=info.name,
                description=info.description,
                category=info.category,
                cost=info.cost,
                when_to_use=info.when_to_use,
                parameters=info.parameters,
                examples=None  # Could be extended to include examples
            )
        else:
            # Basic info only
            detail = ToolDetail(
                name=name,
                description=f"Tool: {name}",
                category="general",
                cost=0.0,
                when_to_use=None,
                parameters=ToolParameterSchema(
                    type="object",
                    properties={},
                    required=[]
                ),
                examples=None
            )
        
        return SuccessResponse(data=detail)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting tool details: {str(e)}")