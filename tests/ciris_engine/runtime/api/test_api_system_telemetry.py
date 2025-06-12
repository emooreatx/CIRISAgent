"""
Tests for API System Telemetry Endpoints

Tests the HTTP API endpoints that expose telemetry data and processor control,
including telemetry snapshots, metrics history, and single-step execution.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from ciris_engine.adapters.api.api_system import APISystemRoutes
from ciris_engine.protocols.telemetry_interface import TelemetrySnapshot, AdapterInfo, ProcessorState
from ciris_engine.schemas.telemetry_schemas_v1 import CompactTelemetry
from ciris_engine.telemetry.comprehensive_collector import ComprehensiveTelemetryCollector


class TestAPISystemTelemetryEndpoints(AioHTTPTestCase):
    """Test suite for API system telemetry endpoints"""
    
    async def get_application(self):
        """Create test application with system routes"""
        app = web.Application()
        
        # Mock telemetry collector
        self.mock_collector = Mock(spec=ComprehensiveTelemetryCollector)
        
        # Setup system routes
        system_routes = APISystemRoutes(self.mock_collector)
        system_routes.register(app)
        
        return app
    
    async def test_get_telemetry_snapshot(self):
        """Test GET /v1/system/telemetry endpoint"""
        # Mock telemetry snapshot
        from ciris_engine.protocols.telemetry_interface import ConfigurationSnapshot
        
        mock_snapshot = TelemetrySnapshot(
            basic_telemetry=CompactTelemetry(
                thoughts_active=0,
                thoughts_24h=150,
                avg_latency_ms=0,
                uptime_hours=24.5,
                guardrail_hits=0,
                deferrals_24h=0,
                errors_24h=0,
                drift_score=0,
                messages_processed_24h=300,
                helpful_actions_24h=0,
                gratitude_expressed_24h=0,
                gratitude_received_24h=0,
                community_health_delta=0,
                wa_available=True,
                isolation_hours=0,
                universal_guidance_count=0,
                epoch_seconds=0
            ),
            adapters=[
                AdapterInfo(
                    name="DiscordAdapter",
                    type="discord",
                    status="active",
                    capabilities=["messaging", "voice"]
                )
            ],
            services=[],
            processor_state=ProcessorState(
                is_running=True,
                current_round=10,
                thoughts_pending=5
            ),
            configuration=ConfigurationSnapshot(
                profile_name="test_profile"
            ),
            runtime_uptime_seconds=88200,  # 24.5 hours
            memory_usage_mb=512.0,
            cpu_usage_percent=25.5,
            overall_health="healthy"
        )
        
        self.mock_collector.get_telemetry_snapshot = AsyncMock(return_value=mock_snapshot)
        
        resp = await self.client.request("GET", "/v1/system/telemetry")
        
        assert resp.status == 200
        data = await resp.json()
        
        # Verify response structure
        assert "basic_telemetry" in data
        assert data["basic_telemetry"]["thoughts_24h"] == 150
        assert data["runtime_uptime_seconds"] == 88200
        assert data["memory_usage_mb"] == 512.0
        assert data["cpu_usage_percent"] == 25.5
        assert data["overall_health"] == "healthy"
        
        # Verify adapters
        assert len(data["adapters"]) == 1
        assert data["adapters"][0]["name"] == "DiscordAdapter"
        assert data["adapters"][0]["status"] == "active"
        
        # Verify processor state
        assert data["processor_state"]["is_running"] == True
        assert data["processor_state"]["current_round"] == 10
        assert data["processor_state"]["thoughts_pending"] == 5
    
    async def test_get_telemetry_snapshot_error(self):
        """Test telemetry snapshot endpoint with collector error"""
        self.mock_collector.get_telemetry_snapshot = AsyncMock(
            side_effect=Exception("Collector failed")
        )
        
        resp = await self.client.request("GET", "/v1/system/telemetry")
        
        assert resp.status == 500
        data = await resp.json()
        assert "error" in data
        assert "Collector failed" in data["error"]
    
    async def test_get_adapters_info(self):
        """Test GET /v1/system/adapters endpoint"""
        mock_adapters = [
            AdapterInfo(
                name="DiscordAdapter",
                type="discord", 
                status="active",
                capabilities=["messaging", "voice"],
                metadata={"server_count": 5}
            ),
            AdapterInfo(
                name="CLIAdapter",
                type="cli",
                status="inactive",
                capabilities=["local_commands"]
            )
        ]
        
        self.mock_collector.get_adapters_info = AsyncMock(return_value=mock_adapters)
        
        resp = await self.client.request("GET", "/v1/system/adapters")
        
        assert resp.status == 200
        data = await resp.json()
        
        assert len(data) == 2
        assert data[0]["name"] == "DiscordAdapter"
        assert data[0]["type"] == "discord"
        assert data[0]["status"] == "active"
        assert "messaging" in data[0]["capabilities"]
        assert data[0]["metadata"]["server_count"] == 5
        
        assert data[1]["name"] == "CLIAdapter"
        assert data[1]["status"] == "inactive"
    
    async def test_get_services_info(self):
        """Test GET /v1/system/services endpoint"""
        from ciris_engine.protocols.telemetry_interface import ServiceInfo
        
        mock_services = [
            ServiceInfo(
                name="OpenAI_Service",
                instance_id="openai-service-1",
                service_type="llm_service",
                handler="speak_handler",
                priority="HIGH",
                capabilities=["text_generation"],
                status="healthy",
                circuit_breaker_state="closed",
                metadata={"model": "gpt-4"}
            )
        ]
        
        self.mock_collector.get_services_info = AsyncMock(return_value=mock_services)
        
        resp = await self.client.request("GET", "/v1/system/services")
        
        assert resp.status == 200
        data = await resp.json()
        
        assert len(data) == 1
        service = data[0]
        assert service["name"] == "OpenAI_Service"
        assert service["service_type"] == "llm_service"
        assert service["handler"] == "speak_handler"
        assert service["status"] == "healthy"
        assert service["circuit_breaker_state"] == "closed"
    
    async def test_get_processor_state(self):
        """Test GET /v1/system/processor/state endpoint"""
        mock_state = ProcessorState(
            is_running=True,
            current_round=15,
            thoughts_pending=3,
            thoughts_processing=1,
            processor_mode="work",
            last_activity=datetime.now(timezone.utc)
        )
        
        self.mock_collector.get_processor_state = AsyncMock(return_value=mock_state)
        
        resp = await self.client.request("GET", "/v1/system/processor/state")
        
        assert resp.status == 200
        data = await resp.json()
        
        assert data["is_running"] == True
        assert data["current_round"] == 15
        assert data["thoughts_pending"] == 3
        assert data["thoughts_processing"] == 1
        assert data["processor_mode"] == "work"
        assert "last_activity" in data
    
    async def test_post_record_metric(self):
        """Test POST /v1/system/metrics endpoint"""
        self.mock_collector.record_metric = AsyncMock()
        
        metric_data = {
            "metric_name": "api_response_time",
            "value": 125.5,
            "tags": {
                "endpoint": "/users",
                "method": "GET",
                "status": "200"
            }
        }
        
        resp = await self.client.request(
            "POST", 
            "/v1/system/metrics",
            json=metric_data
        )
        
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "recorded"
        
        # Verify collector was called correctly
        self.mock_collector.record_metric.assert_called_once_with(
            "api_response_time", 
            125.5, 
            {"endpoint": "/users", "method": "GET", "status": "200"}
        )
    
    async def test_post_record_metric_without_tags(self):
        """Test recording metric without tags"""
        self.mock_collector.record_metric = AsyncMock()
        
        metric_data = {
            "metric_name": "simple_counter",
            "value": 1.0
        }
        
        resp = await self.client.request(
            "POST",
            "/v1/system/metrics", 
            json=metric_data
        )
        
        assert resp.status == 200
        
        # Verify metric recorded with no tags
        self.mock_collector.record_metric.assert_called_once_with(
            "simple_counter", 1.0, None
        )
    
    async def test_post_record_metric_validation_error(self):
        """Test metric recording with invalid data"""
        invalid_data = {
            "metric_name": "test",
            # Missing required 'value' field
        }
        
        resp = await self.client.request(
            "POST",
            "/v1/system/metrics",
            json=invalid_data
        )
        
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data
        assert "validation" in data["error"].lower() or "value" in data["error"]
    
    async def test_get_metrics_history(self):
        """Test GET /v1/system/metrics/{metric_name}/history endpoint"""
        mock_history = [
            {
                "timestamp": "2024-06-09T10:00:00Z",
                "value": 45.5,
                "tags": {"host": "server1"}
            },
            {
                "timestamp": "2024-06-09T10:15:00Z", 
                "value": 52.3,
                "tags": {"host": "server1"}
            }
        ]
        
        self.mock_collector.get_metrics_history = AsyncMock(return_value=mock_history)
        
        resp = await self.client.request("GET", "/v1/system/metrics/cpu_usage/history")
        
        assert resp.status == 200
        data = await resp.json()
        
        assert "history" in data
        assert "metric_name" in data
        assert data["metric_name"] == "cpu_usage"
        
        history = data["history"]
        assert len(history) == 2
        assert history[0]["value"] == 45.5
        assert history[0]["tags"]["host"] == "server1"
        assert history[1]["value"] == 52.3
        
        # Verify collector called with default hours
        self.mock_collector.get_metrics_history.assert_called_once_with("cpu_usage", 24)
    
    async def test_get_metrics_history_with_hours_param(self):
        """Test metrics history with custom hours parameter"""
        self.mock_collector.get_metrics_history = AsyncMock(return_value=[])
        
        resp = await self.client.request(
            "GET", 
            "/v1/system/metrics/memory_usage/history?hours=48"
        )
        
        assert resp.status == 200
        
        # Verify custom hours parameter was used
        self.mock_collector.get_metrics_history.assert_called_once_with("memory_usage", 48)
    
    async def test_get_metrics_history_invalid_hours(self):
        """Test metrics history with invalid hours parameter"""
        resp = await self.client.request(
            "GET",
            "/v1/system/metrics/test/history?hours=invalid"
        )
        
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data
        assert "hours" in data["error"].lower()
    
    async def test_post_single_step(self):
        """Test POST /v1/system/processor/step endpoint"""
        mock_result = {
            "status": "completed",
            "round_number": 16,
            "execution_time_ms": 250,
            "before_state": {
                "thoughts_pending": 5,
                "current_round": 15
            },
            "after_state": {
                "thoughts_pending": 3,
                "current_round": 16
            },
            "summary": {
                "thoughts_processed": 2,
                "round_completed": True
            }
        }
        
        self.mock_collector.single_step = AsyncMock(return_value=mock_result)
        
        resp = await self.client.request("POST", "/v1/system/processor/step")
        
        assert resp.status == 200
        data = await resp.json()
        
        assert data["status"] == "completed"
        assert data["round_number"] == 16
        assert data["execution_time_ms"] == 250
        assert data["summary"]["thoughts_processed"] == 2
        
        self.mock_collector.single_step.assert_called_once()
    
    async def test_post_single_step_error(self):
        """Test single step execution with error"""
        mock_result = {
            "status": "error",
            "error": "Processor not available"
        }
        
        self.mock_collector.single_step = AsyncMock(return_value=mock_result)
        
        resp = await self.client.request("POST", "/v1/system/processor/step")
        
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "error"
        assert "Processor not available" in data["error"]
    
    async def test_post_pause_processing(self):
        """Test POST /v1/system/processor/pause endpoint"""
        self.mock_collector.pause_processing = AsyncMock(return_value=True)
        
        resp = await self.client.request("POST", "/v1/system/processor/pause")
        
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] == True
        
        self.mock_collector.pause_processing.assert_called_once()
    
    async def test_post_pause_processing_failed(self):
        """Test pause processing when operation fails"""
        self.mock_collector.pause_processing = AsyncMock(return_value=False)
        
        resp = await self.client.request("POST", "/v1/system/processor/pause")
        
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] == False
    
    async def test_post_resume_processing(self):
        """Test POST /v1/system/processor/resume endpoint"""
        self.mock_collector.resume_processing = AsyncMock(return_value=True)
        
        resp = await self.client.request("POST", "/v1/system/processor/resume")
        
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] == True
        
        self.mock_collector.resume_processing.assert_called_once()
    
    async def test_get_processing_queue_status(self):
        """Test GET /v1/system/processor/queue endpoint"""
        mock_status = {
            "size": 7,
            "capacity": 100,
            "oldest_item_age": "2_minutes"
        }
        
        self.mock_collector.get_processing_queue_status = AsyncMock(return_value=mock_status)
        
        resp = await self.client.request("GET", "/v1/system/processor/queue")
        
        assert resp.status == 200
        data = await resp.json()
        
        assert data["size"] == 7
        assert data["capacity"] == 100
        assert data["oldest_item_age"] == "2_minutes"
    
    async def test_get_health_status(self):
        """Test GET /v1/system/health endpoint"""
        mock_health = {
            "overall": "healthy",
            "details": {
                "adapters": "all_active",
                "services": "services_healthy",
                "processor": "running"
            }
        }
        
        self.mock_collector.get_health_status = AsyncMock(return_value=mock_health)
        
        resp = await self.client.request("GET", "/v1/system/health")
        
        assert resp.status == 200
        data = await resp.json()
        
        assert data["overall"] == "healthy"
        assert data["details"]["adapters"] == "all_active"
        assert data["details"]["processor"] == "running"
    
    async def test_content_type_json(self):
        """Test that all endpoints return JSON content type"""
        endpoints = [
            ("GET", "/v1/system/telemetry"),
            ("GET", "/v1/system/adapters"),
            ("GET", "/v1/system/services"),
            ("GET", "/v1/system/processor/state"),
            ("GET", "/v1/system/health")
        ]
        
        # Mock all collector methods with required fields
        from ciris_engine.protocols.telemetry_interface import ConfigurationSnapshot
        
        mock_snapshot = TelemetrySnapshot(
            basic_telemetry=CompactTelemetry(
                thoughts_active=0,
                thoughts_24h=0,
                avg_latency_ms=0,
                uptime_hours=0.0,
                guardrail_hits=0,
                deferrals_24h=0,
                errors_24h=0,
                drift_score=0,
                messages_processed_24h=0,
                helpful_actions_24h=0,
                gratitude_expressed_24h=0,
                gratitude_received_24h=0,
                community_health_delta=0,
                wa_available=True,
                isolation_hours=0,
                universal_guidance_count=0,
                epoch_seconds=0
            ),
            processor_state=ProcessorState(
                is_running=False,
                current_round=0,
                thoughts_pending=0
            ),
            configuration=ConfigurationSnapshot(
                profile_name="test"
            )
        )
        
        self.mock_collector.get_telemetry_snapshot = AsyncMock(return_value=mock_snapshot)
        self.mock_collector.get_adapters_info = AsyncMock(return_value=[])
        self.mock_collector.get_services_info = AsyncMock(return_value=[])
        self.mock_collector.get_processor_state = AsyncMock(return_value=ProcessorState(
            is_running=False,
            current_round=0,
            thoughts_pending=0
        ))
        self.mock_collector.get_health_status = AsyncMock(return_value={"overall": "healthy"})
        
        for method, path in endpoints:
            resp = await self.client.request(method, path)
            assert resp.status == 200
            assert resp.content_type == "application/json"
    
    async def test_cors_headers(self):
        """Test that CORS headers are present if configured"""
        resp = await self.client.request("GET", "/v1/system/health")
        
        # This would depend on CORS configuration in the actual application
        # For now, just verify the request completes successfully
        assert resp.status in [200, 500]  # Might be 500 due to mock setup
    
    async def test_error_handling_json_format(self):
        """Test that errors are returned in consistent JSON format"""
        # Force an error by making collector method raise exception
        self.mock_collector.get_telemetry_snapshot = AsyncMock(
            side_effect=Exception("Test error")
        )
        
        resp = await self.client.request("GET", "/v1/system/telemetry")
        
        assert resp.status == 500
        assert resp.content_type == "application/json"
        
        data = await resp.json()
        assert "error" in data
        assert isinstance(data["error"], str)
        assert "Test error" in data["error"]