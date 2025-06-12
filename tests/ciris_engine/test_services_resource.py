"""Unit tests for ServicesResource SDK."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from ciris_sdk.resources.services import ServicesResource
from ciris_sdk.transport import Transport


@pytest.fixture
def mock_transport():
    """Create mock transport."""
    transport = MagicMock(spec=Transport)
    transport.request = AsyncMock()
    return transport


@pytest.fixture
def services_resource(mock_transport):
    """Create services resource with mock transport."""
    return ServicesResource(mock_transport)


@pytest.mark.asyncio
class TestServicesResource:
    """Test ServicesResource functionality."""
    
    async def test_list_services_no_filters(self, services_resource, mock_transport):
        """Test listing services without filters."""
        mock_transport.request.return_value = {
            "handlers": {"test_handler": {"llm": []}},
            "global_services": {"communication": []}
        }
        
        result = await services_resource.list_services()
        
        mock_transport.request.assert_called_once_with(
            "GET", "/v1/runtime/services", params={}
        )
        assert "handlers" in result
        assert "global_services" in result
    
    async def test_list_services_with_filters(self, services_resource, mock_transport):
        """Test listing services with filters."""
        mock_transport.request.return_value = {"filtered": "results"}
        
        result = await services_resource.list_services(
            handler="test_handler", 
            service_type="llm"
        )
        
        mock_transport.request.assert_called_once_with(
            "GET", "/v1/runtime/services", 
            params={"handler": "test_handler", "service_type": "llm"}
        )
        assert result == {"filtered": "results"}
    
    async def test_get_service_health(self, services_resource, mock_transport):
        """Test getting service health."""
        mock_transport.request.return_value = {
            "overall_health": "healthy",
            "total_services": 5,
            "healthy_services": 5,
            "unhealthy_services": 0
        }
        
        result = await services_resource.get_service_health()
        
        mock_transport.request.assert_called_once_with(
            "GET", "/v1/runtime/services/health"
        )
        assert result["overall_health"] == "healthy"
        assert result["total_services"] == 5
    
    async def test_get_selection_explanation(self, services_resource, mock_transport):
        """Test getting service selection explanation."""
        mock_transport.request.return_value = {
            "service_selection_logic": {
                "overview": "test overview",
                "priority_groups": {},
                "selection_strategies": {}
            }
        }
        
        result = await services_resource.get_selection_explanation()
        
        mock_transport.request.assert_called_once_with(
            "GET", "/v1/runtime/services/selection-logic"
        )
        assert "service_selection_logic" in result
    
    async def test_reset_circuit_breakers_no_filter(self, services_resource, mock_transport):
        """Test resetting circuit breakers without service type filter."""
        mock_transport.request.return_value = {"success": True}
        
        result = await services_resource.reset_circuit_breakers()
        
        mock_transport.request.assert_called_once_with(
            "POST", "/v1/runtime/services/circuit-breakers/reset", params={}
        )
        assert result["success"] is True
    
    async def test_reset_circuit_breakers_with_filter(self, services_resource, mock_transport):
        """Test resetting circuit breakers with service type filter."""
        mock_transport.request.return_value = {"success": True}
        
        result = await services_resource.reset_circuit_breakers(service_type="llm")
        
        mock_transport.request.assert_called_once_with(
            "POST", "/v1/runtime/services/circuit-breakers/reset", 
            params={"service_type": "llm"}
        )
        assert result["success"] is True
    
    async def test_update_service_priority_full(self, services_resource, mock_transport):
        """Test updating service priority with all parameters."""
        mock_transport.request.return_value = {"success": True}
        
        result = await services_resource.update_service_priority(
            provider_name="test_provider",
            priority="CRITICAL",
            priority_group=0,
            strategy="FALLBACK"
        )
        
        mock_transport.request.assert_called_once_with(
            "PUT", "/v1/runtime/services/test_provider/priority",
            json={
                "priority": "CRITICAL",
                "priority_group": 0,
                "strategy": "FALLBACK"
            }
        )
        assert result["success"] is True
    
    async def test_update_service_priority_partial(self, services_resource, mock_transport):
        """Test updating service priority with partial parameters."""
        mock_transport.request.return_value = {"success": True}
        
        result = await services_resource.update_service_priority(
            provider_name="test_provider",
            priority="HIGH"
        )
        
        mock_transport.request.assert_called_once_with(
            "PUT", "/v1/runtime/services/test_provider/priority",
            json={"priority": "HIGH"}
        )
        assert result["success"] is True
    
    async def test_get_service_metrics(self, services_resource, mock_transport):
        """Test getting service metrics (placeholder implementation)."""
        result = await services_resource.get_service_metrics("test_service")
        
        assert "message" in result
        assert "not yet implemented" in result["message"]
        # Should not call transport for placeholder
        mock_transport.request.assert_not_called()
    
    async def test_get_llm_services(self, services_resource, mock_transport):
        """Test getting LLM services convenience method."""
        mock_transport.request.return_value = {
            "handlers": {
                "test_handler": {
                    "llm": [
                        {"name": "handler_llm", "priority": "HIGH"}
                    ]
                }
            },
            "global_services": {
                "llm": [
                    {"name": "global_llm", "priority": "NORMAL"}
                ]
            }
        }
        
        result = await services_resource.get_llm_services()
        
        mock_transport.request.assert_called_once_with(
            "GET", "/v1/runtime/services", params={"service_type": "llm"}
        )
        
        assert len(result) == 2
        assert result[0]["scope"] == "handler:test_handler"
        assert result[0]["name"] == "handler_llm"
        assert result[1]["scope"] == "global"
        assert result[1]["name"] == "global_llm"
    
    async def test_get_communication_services(self, services_resource, mock_transport):
        """Test getting communication services convenience method."""
        mock_transport.request.return_value = {
            "handlers": {
                "discord_handler": {
                    "communication": [
                        {"name": "discord_comm", "priority": "HIGH"}
                    ]
                }
            },
            "global_services": {
                "communication": [
                    {"name": "global_comm", "priority": "NORMAL"}
                ]
            }
        }
        
        result = await services_resource.get_communication_services()
        
        mock_transport.request.assert_called_once_with(
            "GET", "/v1/runtime/services", params={"service_type": "communication"}
        )
        
        assert len(result) == 2
        assert result[0]["scope"] == "handler:discord_handler"
        assert result[1]["scope"] == "global"
    
    async def test_get_memory_services(self, services_resource, mock_transport):
        """Test getting memory services convenience method."""
        mock_transport.request.return_value = {
            "handlers": {
                "memory_handler": {
                    "memory": [
                        {"name": "handler_memory", "priority": "HIGH"}
                    ]
                }
            },
            "global_services": {
                "memory": [
                    {"name": "global_memory", "priority": "NORMAL"}
                ]
            }
        }
        
        result = await services_resource.get_memory_services()
        
        mock_transport.request.assert_called_once_with(
            "GET", "/v1/runtime/services", params={"service_type": "memory"}
        )
        
        assert len(result) == 2
        assert result[0]["scope"] == "handler:memory_handler"
        assert result[1]["scope"] == "global"
    
    async def test_diagnose_service_issues_healthy(self, services_resource, mock_transport):
        """Test diagnosing service issues when all healthy."""
        # Mock health response
        mock_transport.request.side_effect = [
            {  # get_service_health response
                "overall_health": "healthy",
                "total_services": 5,
                "healthy_services": 5,
                "unhealthy_services": 0
            },
            {  # list_services response
                "handlers": {
                    "test_handler": {
                        "llm": [{"name": "test_llm"}],
                        "communication": [{"name": "test_comm"}],
                        "memory": [{"name": "test_memory"}],
                        "audit": [{"name": "test_audit"}]
                    }
                },
                "global_services": {}
            }
        ]
        
        result = await services_resource.diagnose_service_issues()
        
        assert result["overall_health"] == "healthy"
        assert result["issues_found"] == 0
        assert len(result["issues"]) == 0
        assert len(result["recommendations"]) == 0
        assert result["service_summary"]["handler_specific_services"] == 4
    
    async def test_diagnose_service_issues_with_problems(self, services_resource, mock_transport):
        """Test diagnosing service issues when problems exist."""
        # Mock responses with issues
        mock_transport.request.side_effect = [
            {  # get_service_health response
                "overall_health": "degraded",
                "total_services": 3,
                "healthy_services": 2,
                "unhealthy_services": 1
            },
            {  # list_services response - missing audit services
                "handlers": {
                    "test_handler": {
                        "llm": [{"name": "test_llm"}],
                        "communication": [{"name": "test_comm"}],
                        "memory": [{"name": "test_memory"}]
                    }
                },
                "global_services": {}
            }
        ]
        
        result = await services_resource.diagnose_service_issues()
        
        assert result["overall_health"] == "degraded"
        assert result["issues_found"] == 2
        assert "1 services are unhealthy" in result["issues"]
        assert "No audit services registered" in result["issues"]
        assert len(result["recommendations"]) == 2
    
    async def test_empty_services_response(self, services_resource, mock_transport):
        """Test handling empty services response."""
        mock_transport.request.return_value = {
            "handlers": {},
            "global_services": {}
        }
        
        result = await services_resource.get_llm_services()
        
        assert result == []
    
    async def test_missing_service_type_in_response(self, services_resource, mock_transport):
        """Test handling missing service type in response."""
        mock_transport.request.return_value = {
            "handlers": {
                "test_handler": {
                    "communication": [{"name": "test_comm"}]
                    # No LLM services
                }
            },
            "global_services": {}
        }
        
        result = await services_resource.get_llm_services()
        
        assert result == []


@pytest.mark.asyncio
class TestServicesResourceErrorHandling:
    """Test error handling in ServicesResource."""
    
    async def test_network_error_handling(self, services_resource, mock_transport):
        """Test handling of network errors."""
        mock_transport.request.side_effect = Exception("Network error")
        
        with pytest.raises(Exception) as exc_info:
            await services_resource.list_services()
        
        assert "Network error" in str(exc_info.value)
    
    async def test_invalid_response_handling(self, services_resource, mock_transport):
        """Test handling of invalid response format."""
        mock_transport.request.return_value = None
        
        # Should handle None response gracefully
        result = await services_resource.get_llm_services()
        assert result == []


@pytest.mark.asyncio  
class TestServicesResourceIntegration:
    """Integration-style tests for ServicesResource."""
    
    async def test_full_workflow(self, services_resource, mock_transport):
        """Test a complete workflow using the services resource."""
        # Simulate a full diagnostic and management workflow
        
        # 1. Check service health
        mock_transport.request.return_value = {
            "overall_health": "degraded",
            "unhealthy_services": 1
        }
        health = await services_resource.get_service_health()
        assert health["overall_health"] == "degraded"
        
        # 2. Reset circuit breakers
        mock_transport.request.return_value = {"success": True}
        reset_result = await services_resource.reset_circuit_breakers()
        assert reset_result["success"] is True
        
        # 3. Update service priority
        mock_transport.request.return_value = {"success": True}
        priority_result = await services_resource.update_service_priority(
            "failing_provider", "LOW", 2, "FALLBACK"
        )
        assert priority_result["success"] is True
        
        # Verify all calls were made
        assert mock_transport.request.call_count == 3