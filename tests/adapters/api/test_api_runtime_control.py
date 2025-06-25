"""Tests for API runtime control endpoints."""
import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from ciris_engine.logic.adapters.api.api_runtime_control import APIRuntimeControlRoutes
from ciris_engine.schemas.services.core.runtime import ProcessorStatus, AdapterStatus


class TestAPIRuntimeControlRoutes(AioHTTPTestCase):
    """Test suite for API runtime control routes."""

    async def get_application(self):
        """Set up test application."""
        self.mock_runtime_control = MagicMock()
        self.routes = APIRuntimeControlRoutes(self.mock_runtime_control)
        
        app = web.Application()
        self.routes.register(app)
        return app

    @unittest_run_loop
    async def test_register_routes(self):
        """Test that all routes are registered correctly."""
        # Just check that routes are registered by trying to access endpoints
        # This is a simpler approach than inspecting the router
        expected_endpoints = [
            ("POST", "/v1/runtime/processor/step"),
            ("POST", "/v1/runtime/processor/pause"),
            ("POST", "/v1/runtime/processor/resume"),
            ("POST", "/v1/runtime/processor/shutdown"),
            ("GET", "/v1/runtime/processor/queue"),
            ("POST", "/v1/runtime/adapters"),
            ("DELETE", "/v1/runtime/adapters/test_adapter"),
            ("GET", "/v1/runtime/adapters"),
            ("GET", "/v1/runtime/adapters/test_adapter"),
            ("GET", "/v1/runtime/config"),
            ("PUT", "/v1/runtime/config"),
            ("POST", "/v1/runtime/config/validate"),
            ("POST", "/v1/runtime/config/reload")
        ]
        
        # Verify routes exist by checking they don't return 404
        for method, path in expected_endpoints:
            resp = await self.client.request(method, path)
            assert resp.status != 404, f"Route {method} {path} not found (got 404)"

    @unittest_run_loop
    async def test_single_step_success(self):
        """Test single step processor control."""
        result = {
            "success": True,
            "operation": "single_step",
            "status": "completed",
            "details": {"steps_executed": 1}
        }
        self.mock_runtime_control.single_step = AsyncMock(return_value=result)
        
        resp = await self.client.request("POST", "/v1/runtime/processor/step")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["success"] is True
        assert data["operation"] == "single_step"
        assert data["status"] == "completed"
        self.mock_runtime_control.single_step.assert_called_once()

    @unittest_run_loop
    async def test_single_step_error(self):
        """Test single step with error."""
        self.mock_runtime_control.single_step = AsyncMock(side_effect=Exception("Test error"))
        
        resp = await self.client.request("POST", "/v1/runtime/processor/step")
        assert resp.status == 500
        
        data = await resp.json()
        assert "error" in data
        assert "Test error" in data["error"]

    @unittest_run_loop
    async def test_pause_processing(self):
        """Test pause processing."""
        result = {
            "success": True,
            "operation": "pause",
            "status": ProcessorStatus.PAUSED.value,
            "details": {}
        }
        self.mock_runtime_control.pause_processing = AsyncMock(return_value=result)
        
        resp = await self.client.request("POST", "/v1/runtime/processor/pause")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["success"] is True
        assert data["status"] == ProcessorStatus.PAUSED.value

    @unittest_run_loop
    async def test_resume_processing(self):
        """Test resume processing."""
        self.mock_runtime_control.resume_processing = AsyncMock(return_value={"status": "resumed"})
        
        resp = await self.client.request("POST", "/v1/runtime/processor/resume")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == "resumed"

    @unittest_run_loop
    async def test_shutdown_runtime(self):
        """Test shutdown runtime."""
        self.mock_runtime_control.shutdown_runtime = AsyncMock(return_value={"status": "shutting_down"})
        
        resp = await self.client.request("POST", "/v1/runtime/processor/shutdown")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == "shutting_down"

    @unittest_run_loop
    async def test_get_queue_status(self):
        """Test get queue status."""
        self.mock_runtime_control.get_processor_queue_status = AsyncMock(return_value={
            "queue_size": 5,
            "processing": True
        })
        
        resp = await self.client.request("GET", "/v1/runtime/processor/queue")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["queue_size"] == 5
        assert data["processing"] is True

    @unittest_run_loop
    async def test_load_adapter(self):
        """Test load adapter."""
        result = {
            "success": True,
            "adapter_id": "test_adapter",
            "adapter_type": "cli",
            "status": AdapterStatus.ACTIVE.value,
            "services_registered": ["communication"]
        }
        self.mock_runtime_control.load_adapter = AsyncMock(return_value=result)
        
        payload = {"adapter_type": "cli", "adapter_id": "test_adapter", "config": {}}
        resp = await self.client.request("POST", "/v1/runtime/adapters", 
                                       data=json.dumps(payload),
                                       headers={"Content-Type": "application/json"})
        assert resp.status == 200
        
        data = await resp.json()
        assert data["success"] is True
        assert data["adapter_id"] == "test_adapter"
        assert data["adapter_type"] == "cli"
        assert data["status"] == AdapterStatus.ACTIVE.value

    @unittest_run_loop
    async def test_unload_adapter(self):
        """Test unload adapter."""
        self.mock_runtime_control.unload_adapter = AsyncMock(return_value={"status": "unloaded"})
        
        resp = await self.client.request("DELETE", "/v1/runtime/adapters/test_adapter")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == "unloaded"

    @unittest_run_loop
    async def test_list_adapters(self):
        """Test list adapters."""
        self.mock_runtime_control.list_adapters = AsyncMock(return_value={
            "adapters": [
                {"id": "adapter1", "type": "cli", "status": "active"},
                {"id": "adapter2", "type": "api", "status": "active"}
            ]
        })
        
        resp = await self.client.request("GET", "/v1/runtime/adapters")
        assert resp.status == 200
        
        data = await resp.json()
        assert len(data["adapters"]) == 2
        assert data["adapters"][0]["id"] == "adapter1"

    @unittest_run_loop
    async def test_get_adapter_info(self):
        """Test get adapter info."""
        self.mock_runtime_control.get_adapter_info = AsyncMock(return_value={
            "id": "test_adapter",
            "type": "cli",
            "status": "active",
            "config": {}
        })
        
        resp = await self.client.request("GET", "/v1/runtime/adapters/test_adapter")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["id"] == "test_adapter"
        assert data["type"] == "cli"

    @unittest_run_loop
    async def test_get_config(self):
        """Test get configuration."""
        self.mock_runtime_control.get_config = AsyncMock(return_value={
            "database": {"db_filename": "test.db"},
            "log_level": "INFO"
        })
        
        resp = await self.client.request("GET", "/v1/runtime/config")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["database"]["db_filename"] == "test.db"
        assert data["log_level"] == "INFO"

    @unittest_run_loop
    async def test_update_config(self):
        """Test update configuration."""
        self.mock_runtime_control.update_config = AsyncMock(return_value={
            "status": "updated",
            "changes": ["log_level"]
        })
        
        payload = {"path": "log_level", "value": "DEBUG"}
        resp = await self.client.request("PUT", "/v1/runtime/config",
                                       data=json.dumps(payload),
                                       headers={"Content-Type": "application/json"})
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == "updated"
        assert "log_level" in data["changes"]

    @unittest_run_loop
    async def test_validate_config(self):
        """Test validate configuration."""
        self.mock_runtime_control.validate_config = AsyncMock(return_value={
            "valid": True,
            "errors": []
        })
        
        payload = {"config_data": {"log_level": "DEBUG"}}
        resp = await self.client.request("POST", "/v1/runtime/config/validate",
                                       data=json.dumps(payload),
                                       headers={"Content-Type": "application/json"})
        assert resp.status == 200
        
        data = await resp.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0

    @unittest_run_loop
    async def test_reload_config(self):
        """Test reload configuration."""
        self.mock_runtime_control.reload_config = AsyncMock(return_value={
            "status": "reloaded",
            "config_path": "/path/to/config.json"
        })
        
        resp = await self.client.request("POST", "/v1/runtime/config/reload")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == "reloaded"

    @pytest.mark.skip(reason="Profile endpoints not implemented - identity is now graph-based")
    @unittest_run_loop
    async def test_list_profiles(self):
        """Test list profiles."""
        pass  # Profile endpoints not implemented

    @pytest.mark.skip(reason="Profile endpoints not implemented - identity is now graph-based")
    @unittest_run_loop
    async def test_load_profile(self):
        """Test load profile."""
        pass  # Profile endpoints not implemented

    @pytest.mark.skip(reason="Profile endpoints not implemented - identity is now graph-based")
    @unittest_run_loop
    async def test_get_profile(self):
        """Test get profile."""
        pass  # Profile endpoints not implemented

    @pytest.mark.skip(reason="Profile endpoints not implemented - identity is now graph-based")
    @unittest_run_loop
    async def test_create_profile(self):
        """Test create profile - currently not implemented."""
        pass  # Profile endpoints not implemented

    @unittest_run_loop
    async def test_invalid_json_payload(self):
        """Test handling of invalid JSON payload."""
        resp = await self.client.request("POST", "/v1/runtime/adapters",
                                       data="invalid json",
                                       headers={"Content-Type": "application/json"})
        assert resp.status == 400

    @unittest_run_loop
    async def test_method_not_allowed(self):
        """Test method not allowed responses."""
        resp = await self.client.request("GET", "/v1/runtime/processor/step")
        assert resp.status == 405