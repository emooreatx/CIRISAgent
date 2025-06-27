"""
Tests for Tool Discovery API endpoints.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from ciris_engine.schemas.adapters.tools import ToolInfo, ToolParameterSchema
from ciris_engine.api.routes.tools import (
    ToolsOverview, ToolSummary, ToolDetail, ToolCategory, ToolUsageStats
)


@pytest.fixture
def mock_tool_service():
    """Create a mock tool service."""
    service = AsyncMock()
    
    # Basic tool list
    service.list_tools = AsyncMock(return_value=[
        "calculator",
        "weather",
        "file_reader",
        "web_search"
    ])
    
    # Tool info mapping
    tool_infos = {
        "calculator": ToolInfo(
            name="calculator",
            description="Perform mathematical calculations",
            parameters=ToolParameterSchema(
                type="object",
                properties={
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                required=["expression"]
            ),
            category="analysis",
            cost=0.001,
            when_to_use="Use when you need to perform calculations"
        ),
        "weather": ToolInfo(
            name="weather",
            description="Get current weather information",
            parameters=ToolParameterSchema(
                type="object",
                properties={
                    "location": {
                        "type": "string",
                        "description": "City or location name"
                    }
                },
                required=["location"]
            ),
            category="integration",
            cost=0.01,
            when_to_use="Use to check weather conditions"
        ),
        "file_reader": ToolInfo(
            name="file_reader",
            description="Read contents of a file",
            parameters=ToolParameterSchema(
                type="object",
                properties={
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    }
                },
                required=["path"]
            ),
            category="system",
            cost=0.0
        ),
        "web_search": ToolInfo(
            name="web_search",
            description="Search the web for information",
            parameters=ToolParameterSchema(
                type="object",
                properties={
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 10
                    }
                },
                required=["query"]
            ),
            category="integration",
            cost=0.05,
            when_to_use="Use to find information on the internet"
        )
    }
    
    async def get_tool_info_mock(name: str):
        if name in tool_infos:
            return tool_infos[name]
        raise ValueError(f"Tool {name} not found")
    
    service.get_tool_info = get_tool_info_mock
    
    return service


@pytest.fixture
def app_with_tools(mock_tool_service, mock_auth_service):
    """Create FastAPI app with tools routes."""
    from fastapi import FastAPI
    from ciris_engine.api.routes.tools import router
    
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add services to app state
    app.state.tool_service = mock_tool_service
    app.state.auth_service = mock_auth_service
    app.state.telemetry_service = None  # Optional service
    
    return app


class TestListTools:
    """Test GET /v1/tools endpoint."""
    
    def test_list_all_tools(self, app_with_tools, observer_headers):
        """Test listing all available tools."""
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        assert data["total_tools"] == 4
        assert len(data["tools"]) == 4
        assert set(data["categories"]) == {"analysis", "integration", "system"}
        
        # Check tool summaries
        tool_names = [t["name"] for t in data["tools"]]
        assert set(tool_names) == {"calculator", "weather", "file_reader", "web_search"}
        
        # Check a specific tool summary
        calc_tool = next(t for t in data["tools"] if t["name"] == "calculator")
        assert calc_tool["description"] == "Perform mathematical calculations"
        assert calc_tool["category"] == "analysis"
        assert calc_tool["cost"] == 0.001
    
    def test_list_tools_by_category(self, app_with_tools, observer_headers):
        """Test filtering tools by category."""
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools?category=integration",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        assert data["total_tools"] == 2
        assert len(data["tools"]) == 2
        
        tool_names = [t["name"] for t in data["tools"]]
        assert set(tool_names) == {"weather", "web_search"}
    
    def test_list_tools_no_service(self, mock_auth_service, observer_headers):
        """Test when no tool service is available."""
        from fastapi import FastAPI
        from ciris_engine.api.routes.tools import router
        
        app = FastAPI()
        app.include_router(router, prefix="/v1")
        app.state.tool_service = None
        app.state.auth_service = mock_auth_service
        
        client = TestClient(app)
        
        response = client.get(
            "/v1/tools",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        assert data["total_tools"] == 0
        assert data["tools"] == []
        assert data["categories"] == []
    
    def test_list_tools_basic_service(self, mock_auth_service, observer_headers):
        """Test with basic tool service (no get_tool_info method)."""
        from fastapi import FastAPI
        from ciris_engine.api.routes.tools import router
        
        # Create basic service with only list_tools
        basic_service = AsyncMock()
        basic_service.list_tools = AsyncMock(return_value=["tool1", "tool2"])
        # Ensure hasattr returns False for get_tool_info
        basic_service.get_tool_info = None
        del basic_service.get_tool_info
        
        app = FastAPI()
        app.include_router(router, prefix="/v1")
        app.state.tool_service = basic_service
        app.state.auth_service = mock_auth_service
        
        client = TestClient(app)
        
        response = client.get(
            "/v1/tools",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        assert data["total_tools"] == 2
        assert len(data["tools"]) == 2
        assert all(t["category"] == "general" for t in data["tools"])


class TestGetToolDetails:
    """Test GET /v1/tools/{name} endpoint."""
    
    def test_get_tool_details(self, app_with_tools, observer_headers):
        """Test getting detailed tool information."""
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools/calculator",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        assert data["name"] == "calculator"
        assert data["description"] == "Perform mathematical calculations"
        assert data["category"] == "analysis"
        assert data["cost"] == 0.001
        assert data["when_to_use"] == "Use when you need to perform calculations"
        
        # Check parameters schema
        params = data["parameters"]
        assert params["type"] == "object"
        assert "expression" in params["properties"]
        assert params["required"] == ["expression"]
    
    def test_get_tool_not_found(self, app_with_tools, observer_headers):
        """Test getting details for non-existent tool."""
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools/nonexistent",
            headers=observer_headers
        )
        
        assert response.status_code == 404
        assert "Tool 'nonexistent' not found" in response.json()["detail"]
    
    def test_get_tool_no_service(self, mock_auth_service, observer_headers):
        """Test when no tool service is available."""
        from fastapi import FastAPI
        from ciris_engine.api.routes.tools import router
        
        app = FastAPI()
        app.include_router(router, prefix="/v1")
        app.state.tool_service = None
        app.state.auth_service = mock_auth_service
        
        client = TestClient(app)
        
        response = client.get(
            "/v1/tools/calculator",
            headers=observer_headers
        )
        
        assert response.status_code == 404
        assert "Tool service not available" in response.json()["detail"]


class TestGetToolCategories:
    """Test GET /v1/tools/categories endpoint."""
    
    def test_get_categories(self, app_with_tools, observer_headers):
        """Test getting tool categories."""
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools/categories",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        categories = response.json()["data"]
        
        assert len(categories) == 3
        
        # Check categories are sorted
        cat_names = [c["name"] for c in categories]
        assert cat_names == sorted(cat_names)
        
        # Check specific category
        integration_cat = next(c for c in categories if c["name"] == "integration")
        assert integration_cat["tool_count"] == 2
        assert set(integration_cat["tools"]) == {"weather", "web_search"}
        assert integration_cat["description"] == "External service integration tools"
    
    def test_get_categories_no_service(self, mock_auth_service, observer_headers):
        """Test categories when no tool service available."""
        from fastapi import FastAPI
        from ciris_engine.api.routes.tools import router
        
        app = FastAPI()
        app.include_router(router, prefix="/v1")
        app.state.tool_service = None
        app.state.auth_service = mock_auth_service
        
        client = TestClient(app)
        
        response = client.get(
            "/v1/tools/categories",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        assert response.json()["data"] == []


class TestGetToolUsage:
    """Test GET /v1/tools/usage endpoint."""
    
    def test_get_all_usage(self, app_with_tools, observer_headers):
        """Test getting usage stats for all tools."""
        # Add telemetry service
        app_with_tools.state.telemetry_service = AsyncMock()
        
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools/usage",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        stats = response.json()["data"]
        
        assert len(stats) == 4
        
        # Check stat structure
        for stat in stats:
            assert "tool_name" in stat
            assert "total_calls" in stat
            assert "success_count" in stat
            assert "failure_count" in stat
            assert "average_duration_ms" in stat
            assert "last_used" in stat
    
    def test_get_specific_tool_usage(self, app_with_tools, observer_headers):
        """Test getting usage stats for specific tool."""
        app_with_tools.state.telemetry_service = AsyncMock()
        
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools/usage?tool_name=calculator",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        stats = response.json()["data"]
        
        assert len(stats) == 1
        assert stats[0]["tool_name"] == "calculator"
    
    def test_get_usage_tool_not_found(self, app_with_tools, observer_headers):
        """Test usage stats for non-existent tool."""
        app_with_tools.state.telemetry_service = AsyncMock()
        
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools/usage?tool_name=nonexistent",
            headers=observer_headers
        )
        
        assert response.status_code == 404
        assert "Tool 'nonexistent' not found" in response.json()["detail"]
    
    def test_get_usage_no_telemetry(self, app_with_tools, observer_headers):
        """Test usage when no telemetry service available."""
        # Remove telemetry service
        if hasattr(app_with_tools.state, 'telemetry_service'):
            delattr(app_with_tools.state, 'telemetry_service')
        
        client = TestClient(app_with_tools)
        
        response = client.get(
            "/v1/tools/usage",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        assert response.json()["data"] == []


class TestToolsAuth:
    """Test authentication for tools endpoints."""
    
    def test_requires_auth(self, app_with_tools):
        """Test that endpoints require authentication."""
        client = TestClient(app_with_tools)
        
        endpoints = [
            "/v1/tools",
            "/v1/tools/calculator",
            "/v1/tools/categories",
            "/v1/tools/usage"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401