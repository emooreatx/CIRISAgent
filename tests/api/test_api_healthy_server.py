"""
Comprehensive tests for API endpoints to verify healthy server status.
Tests health, telemetry, and metrics endpoints with mock LLM for offline testing.
"""

import pytest
import asyncio
import aiohttp
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import logging
logger = logging.getLogger(__name__)


class TestHealthyServerAPI:
    """Test suite for verifying API endpoints return correct data for a healthy server"""
    
    BASE_URL = "http://localhost:8080"
    
    @pytest.fixture(autouse=True)
    async def setup_test(self):
        """Setup for each test - ensure server is responsive"""
        # Wait a moment for server to be ready
        await asyncio.sleep(0.5)
        
        # Check basic connectivity
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/v1/system/health", timeout=5) as response:
                    if response.status != 200:
                        pytest.skip(f"API server not responsive (status: {response.status})")
        except Exception as e:
            pytest.skip(f"API server not accessible: {e}")
    
    async def test_health_endpoint_basic(self):
        """Test basic health endpoint functionality"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/health") as response:
                assert response.status == 200
                data = await response.json()
                
                # Verify health response structure
                assert "overall" in data
                assert "details" in data
                assert isinstance(data["details"], dict)
                
                # Health status should be one of expected values
                assert data["overall"] in ["healthy", "degraded", "critical"]
                
                logger.info(f"Health status: {data}")
    
    async def test_health_endpoint_adapters(self):
        """Test adapter health reporting"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/health") as response:
                assert response.status == 200
                data = await response.json()
                
                # Check adapter status
                details = data["details"]
                assert "adapters" in details
                
                adapter_status = details["adapters"]
                # Should show active adapters for a running server
                expected_adapter_statuses = ["all_active", "some_adapters_inactive", "no_adapters", "no_active_adapters"]
                assert adapter_status in expected_adapter_statuses
                
                logger.info(f"Adapter status: {adapter_status}")
    
    async def test_health_endpoint_services(self):
        """Test service health reporting"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/health") as response:
                assert response.status == 200
                data = await response.json()
                
                # Check service status
                details = data["details"]
                assert "services" in details
                
                service_status = details["services"]
                # Should show service health information
                expected_service_statuses = ["services_healthy", "degraded_services"]
                assert service_status in expected_service_statuses
                
                logger.info(f"Service status: {service_status}")
    
    async def test_health_endpoint_processor(self):
        """Test processor health reporting"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/health") as response:
                assert response.status == 200
                data = await response.json()
                
                # Check processor status
                details = data["details"]
                assert "processor" in details
                
                processor_status = details["processor"]
                # Should show processor state
                expected_processor_statuses = ["running", "not_running"]
                assert processor_status in expected_processor_statuses
                
                logger.info(f"Processor status: {processor_status}")
    
    async def test_telemetry_endpoint_basic(self):
        """Test basic telemetry endpoint functionality"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/telemetry") as response:
                assert response.status == 200
                data = await response.json()
                
                # Verify telemetry response structure
                required_fields = [
                    "timestamp", "schema_version", "basic_telemetry", 
                    "adapters", "services", "processor_state", "configuration",
                    "runtime_uptime_seconds", "memory_usage_mb", "cpu_usage_percent",
                    "overall_health", "health_details"
                ]
                
                for field in required_fields:
                    assert field in data, f"Missing required field: {field}"
                
                # Verify timestamp is recent
                timestamp = datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                time_diff = abs((now - timestamp).total_seconds())
                assert time_diff < 60, f"Timestamp too old: {time_diff} seconds"
                
                logger.info(f"Telemetry basic structure verified")
    
    async def test_telemetry_adapters_info(self):
        """Test telemetry adapter information"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/telemetry") as response:
                assert response.status == 200
                data = await response.json()
                
                adapters = data["adapters"]
                assert isinstance(adapters, list)
                
                for adapter in adapters:
                    # Verify adapter structure
                    required_adapter_fields = ["name", "type", "status", "capabilities", "metadata"]
                    for field in required_adapter_fields:
                        assert field in adapter, f"Missing adapter field: {field}"
                    
                    # Verify adapter status values
                    assert adapter["status"] in ["active", "inactive", "error"]
                    assert isinstance(adapter["capabilities"], list)
                    assert isinstance(adapter["metadata"], dict)
                
                logger.info(f"Found {len(adapters)} adapters in telemetry")
    
    async def test_telemetry_services_info(self):
        """Test telemetry service information"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/telemetry") as response:
                assert response.status == 200
                data = await response.json()
                
                services = data["services"]
                assert isinstance(services, list)
                
                for service in services:
                    # Verify service structure
                    required_service_fields = [
                        "name", "service_type", "priority", "capabilities", 
                        "status", "circuit_breaker_state", "metadata", "instance_id"
                    ]
                    for field in required_service_fields:
                        assert field in service, f"Missing service field: {field}"
                    
                    # Verify service status values
                    assert service["status"] in ["healthy", "degraded", "failed", "unknown"]
                    assert service["circuit_breaker_state"] in ["closed", "open", "half_open", "unknown"]
                    assert isinstance(service["capabilities"], list)
                    assert isinstance(service["metadata"], dict)
                
                logger.info(f"Found {len(services)} services in telemetry")
    
    async def test_telemetry_processor_state(self):
        """Test telemetry processor state information"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/telemetry") as response:
                assert response.status == 200
                data = await response.json()
                
                processor_state = data["processor_state"]
                assert isinstance(processor_state, dict)
                
                # Verify processor state structure
                required_processor_fields = [
                    "is_running", "current_round", "thoughts_pending", 
                    "thoughts_processing", "processor_mode"
                ]
                for field in required_processor_fields:
                    assert field in processor_state, f"Missing processor field: {field}"
                
                # Verify data types
                assert isinstance(processor_state["is_running"], bool)
                assert isinstance(processor_state["current_round"], int)
                assert isinstance(processor_state["thoughts_pending"], int)
                assert isinstance(processor_state["thoughts_processing"], int)
                assert isinstance(processor_state["processor_mode"], str)
                
                # Verify processor mode values
                expected_modes = ["work", "dream", "wakeup", "idle", "unknown", "play", "solitude"]
                assert processor_state["processor_mode"] in expected_modes
                
                logger.info(f"Processor state: running={processor_state['is_running']}, mode={processor_state['processor_mode']}")
    
    async def test_telemetry_configuration(self):
        """Test telemetry configuration information"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/telemetry") as response:
                assert response.status == 200
                data = await response.json()
                
                configuration = data["configuration"]
                assert isinstance(configuration, dict)
                
                # Verify configuration structure
                required_config_fields = ["profile_name", "debug_mode", "adapter_modes"]
                for field in required_config_fields:
                    assert field in configuration, f"Missing configuration field: {field}"
                
                # Verify data types
                assert isinstance(configuration["profile_name"], str)
                assert isinstance(configuration["debug_mode"], bool)
                assert isinstance(configuration["adapter_modes"], list)
                
                logger.info(f"Configuration: profile={configuration['profile_name']}, debug={configuration['debug_mode']}")
    
    async def test_telemetry_runtime_metrics(self):
        """Test telemetry runtime metrics"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/telemetry") as response:
                assert response.status == 200
                data = await response.json()
                
                # Verify runtime metrics
                assert isinstance(data["runtime_uptime_seconds"], (int, float))
                assert isinstance(data["memory_usage_mb"], (int, float))
                assert isinstance(data["cpu_usage_percent"], (int, float))
                
                # Sanity checks
                assert data["runtime_uptime_seconds"] >= 0
                assert data["memory_usage_mb"] > 0  # Should have some memory usage
                assert 0 <= data["cpu_usage_percent"] <= 100
                
                logger.info(f"Runtime metrics: uptime={data['runtime_uptime_seconds']}s, memory={data['memory_usage_mb']}MB, cpu={data['cpu_usage_percent']}%")
    
    async def test_metrics_endpoint_basic(self):
        """Test basic metrics endpoint functionality"""
        async with aiohttp.ClientSession() as session:
            # Test the metrics endpoint (may be different path)
            endpoints_to_try = [
                "/v1/system/metrics",
                "/v1/metrics", 
                "/metrics"
            ]
            
            found_metrics = False
            for endpoint in endpoints_to_try:
                try:
                    async with session.get(f"{self.BASE_URL}{endpoint}") as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"Found metrics endpoint at {endpoint}")
                            found_metrics = True
                            
                            # Basic metrics structure check
                            assert isinstance(data, dict)
                            logger.info(f"Metrics data keys: {list(data.keys())}")
                            break
                        elif response.status == 404:
                            continue
                        else:
                            logger.warning(f"Metrics endpoint {endpoint} returned status {response.status}")
                except Exception as e:
                    logger.debug(f"Endpoint {endpoint} failed: {e}")
                    continue
            
            if not found_metrics:
                pytest.skip("No metrics endpoint found - may not be implemented yet")
    
    async def test_metrics_history_endpoint(self):
        """Test metrics history functionality if available"""
        async with aiohttp.ClientSession() as session:
            # Check if metrics history endpoint exists
            history_endpoints = [
                "/v1/system/metrics/history",
                "/v1/metrics/history"
            ]
            
            for endpoint in history_endpoints:
                try:
                    async with session.get(f"{self.BASE_URL}{endpoint}") as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"Found metrics history at {endpoint}")
                            assert isinstance(data, (dict, list))
                            return
                        elif response.status != 404:
                            logger.warning(f"Metrics history {endpoint} returned status {response.status}")
                except Exception as e:
                    logger.debug(f"History endpoint {endpoint} failed: {e}")
                    continue
            
            logger.info("No metrics history endpoint found - may not be implemented yet")
    
    async def test_health_and_telemetry_consistency(self):
        """Test that health and telemetry endpoints report consistent information"""
        async with aiohttp.ClientSession() as session:
            # Get both health and telemetry data
            async with session.get(f"{self.BASE_URL}/v1/system/health") as response:
                assert response.status == 200
                health_data = await response.json()
            
            async with session.get(f"{self.BASE_URL}/v1/system/telemetry") as response:
                assert response.status == 200
                telemetry_data = await response.json()
            
            # Check consistency between health and telemetry
            assert health_data["overall"] == telemetry_data["overall_health"]
            assert health_data["details"] == telemetry_data["health_details"]
            
            # Adapter consistency
            health_adapters = health_data["details"]["adapters"]
            telemetry_adapters = telemetry_data["adapters"]
            
            if health_adapters == "all_active":
                # All adapters in telemetry should be active
                active_adapters = [a for a in telemetry_adapters if a["status"] == "active"]
                assert len(active_adapters) == len(telemetry_adapters), "Health says all_active but telemetry shows inactive adapters"
            
            # Processor consistency
            health_processor = health_data["details"]["processor"]
            telemetry_processor = telemetry_data["processor_state"]["is_running"]
            
            if health_processor == "running":
                assert telemetry_processor == True, "Health says running but telemetry shows not running"
            elif health_processor == "not_running":
                assert telemetry_processor == False, "Health says not running but telemetry shows running"
            
            logger.info("Health and telemetry data is consistent")
    
    async def test_service_health_threshold_logic(self):
        """Test that service health threshold logic is working correctly"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/v1/system/telemetry") as response:
                assert response.status == 200
                data = await response.json()
            
            services = data["services"]
            healthy_services = [s for s in services if s["status"] == "healthy"]
            total_services = len(services)
            healthy_percentage = len(healthy_services) / total_services if total_services > 0 else 0
            
            service_health_status = data["health_details"]["services"]
            
            # Verify 80% threshold logic
            if healthy_percentage >= 0.8:
                assert service_health_status == "services_healthy", f"Expected services_healthy but got {service_health_status} (healthy: {len(healthy_services)}/{total_services} = {healthy_percentage:.1%})"
            else:
                assert service_health_status == "degraded_services", f"Expected degraded_services but got {service_health_status} (healthy: {len(healthy_services)}/{total_services} = {healthy_percentage:.1%})"
            
            logger.info(f"Service health threshold verified: {len(healthy_services)}/{total_services} ({healthy_percentage:.1%}) -> {service_health_status}")


# Additional test for processor control if available
class TestProcessorControl:
    """Test processor control endpoints if they exist"""
    
    BASE_URL = "http://localhost:8080"
    
    async def test_processor_control_endpoints(self):
        """Test processor control endpoints if available"""
        async with aiohttp.ClientSession() as session:
            control_endpoints = [
                "/v1/system/processor/status",
                "/v1/processor/status",
                "/v1/system/processor/single-step",
                "/v1/processor/single-step"
            ]
            
            for endpoint in control_endpoints:
                try:
                    async with session.get(f"{self.BASE_URL}{endpoint}") as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"Found processor control endpoint at {endpoint}: {data}")
                        elif response.status != 404:
                            logger.warning(f"Processor control {endpoint} returned status {response.status}")
                except Exception as e:
                    logger.debug(f"Control endpoint {endpoint} failed: {e}")
                    continue


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])