#!/usr/bin/env python3
"""
Comprehensive unit tests for CIRIS SDK v1 API endpoints.

Tests all 35 endpoints through the SDK with proper authentication.
"""
import asyncio
import pytest
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from ciris_sdk import CIRISClient
from ciris_sdk.exceptions import CIRISAuthenticationError, CIRISNotFoundError, CIRISValidationError, CIRISAPIError
from ciris_sdk.models import GraphNode


class TestCIRISSDKEndpoints:
    """Test suite for all CIRIS API endpoints through the SDK."""
    
    @pytest.fixture
    async def client(self):
        """Create authenticated CIRIS client."""
        async with CIRISClient(
            base_url="http://localhost:8080",
            timeout=30.0
        ) as client:
            # Authenticate with default credentials
            response = await client.auth.login("admin", "ciris_admin_password")
            # SDK doesn't auto-update transport token yet, so manually set it
            client._transport.set_api_key(response.access_token)
            yield client
    
    @pytest.fixture
    async def unauthenticated_client(self):
        """Create unauthenticated CIRIS client."""
        async with CIRISClient(
            base_url="http://localhost:8080",
            timeout=30.0
        ) as client:
            yield client

    # ========== Authentication Tests (4 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_auth_login(self, unauthenticated_client):
        """Test POST /v1/auth/login."""
        # Test successful login
        response = await unauthenticated_client.auth.login("admin", "ciris_admin_password")
        assert response.access_token
        assert response.token_type == "Bearer"
        assert response.role == "SYSTEM_ADMIN"
        assert response.user_id == "SYSTEM_ADMIN"
        # SDK doesn't auto-update transport token yet, so manually set it for later use
        unauthenticated_client._transport.set_api_key(response.access_token)
        
        # Test failed login - SDK raises generic CIRISAPIError for 401
        from ciris_sdk.exceptions import CIRISAPIError
        with pytest.raises(CIRISAPIError) as exc_info:
            await unauthenticated_client.auth.login("invalid", "wrong")
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_auth_logout(self, client):
        """Test POST /v1/auth/logout."""
        # Should succeed with authenticated client
        await client.auth.logout()
        
        # After logout, requests should fail - SDK raises generic CIRISAPIError for 401
        with pytest.raises(CIRISAPIError) as exc_info:
            await client.agent.get_identity()
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_auth_me(self, client):
        """Test GET /v1/auth/me."""
        user_info = await client.auth.get_current_user()
        assert user_info.user_id == "SYSTEM_ADMIN"
        assert user_info.username == "SYSTEM_ADMIN"
        assert user_info.role == "SYSTEM_ADMIN"
        assert len(user_info.permissions) > 0
    
    @pytest.mark.asyncio
    async def test_auth_refresh(self, client):
        """Test POST /v1/auth/refresh."""
        # Get current token
        old_token = client._transport.api_key
        
        # Refresh token
        response = await client.auth.refresh_token()
        assert response.access_token
        assert response.access_token != old_token
        assert response.role == "SYSTEM_ADMIN"

    # ========== Agent Tests (5 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_agent_identity(self, client):
        """Test GET /v1/agent/identity."""
        identity = await client.agent.get_identity()
        assert identity.agent_id
        assert identity.name
        assert identity.version
        assert identity.created_at
    
    @pytest.mark.asyncio
    async def test_agent_status(self, client):
        """Test GET /v1/agent/status."""
        status = await client.agent.get_status()
        assert status.cognitive_state in ["WAKEUP", "WORK", "PLAY", "SOLITUDE", "DREAM", "SHUTDOWN"]
        assert status.processor_state
        assert isinstance(status.uptime_seconds, (int, float))
        assert status.uptime_seconds >= 0
    
    @pytest.mark.asyncio
    async def test_agent_interact(self, client):
        """Test POST /v1/agent/interact."""
        response = await client.agent.interact("Hello, CIRIS! What is 2+2?")
        assert response.response
        assert response.interaction_id
        assert response.timestamp
        assert response.processing_time_ms >= 0
    
    @pytest.mark.asyncio
    async def test_agent_history(self, client):
        """Test GET /v1/agent/history."""
        # First create an interaction
        await client.agent.interact("Test message for history")
        
        # Then get history
        history = await client.agent.get_history(limit=10)
        assert history.interactions
        assert len(history.interactions) <= 10
        assert history.total >= 0
    
    @pytest.mark.asyncio
    async def test_agent_stream(self, client):
        """Test WebSocket /v1/agent/stream."""
        # WebSocket testing requires special handling
        # For now, just verify the endpoint exists
        assert hasattr(client.agent, 'stream')

    # ========== Memory Tests (4 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_memory_store(self, client):
        """Test POST /v1/memory/store."""
        # Create a test node
        node = GraphNode(
            id=f"test-node-{datetime.now().timestamp()}",
            type="concept",
            scope="local",
            attributes={
                "test": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "data": "Test memory node"
            }
        )
        
        result = await client.memory.store(node)
        assert result.success
        assert result.node_id
        assert result.operation == "MEMORIZE"
    
    @pytest.mark.asyncio
    async def test_memory_query(self, client):
        """Test POST /v1/memory/query."""
        # Query for recent memories
        nodes = await client.memory.query(
            query="test",
            limit=10
        )
        assert isinstance(nodes, list)
        assert len(nodes) <= 10
    
    @pytest.mark.asyncio
    async def test_memory_recall(self, client):
        """Test GET /v1/memory/recall/{node_id}."""
        # First store a node
        node = GraphNode(
            id=f"test-recall-{datetime.now().timestamp()}",
            type="concept",
            scope="local",
            attributes={
                "test": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        )
        result = await client.memory.store(node)
        
        # Then recall it
        recalled = await client.memory.recall(result.node_id)
        assert recalled.id == result.node_id
        assert recalled.type == "concept"
    
    @pytest.mark.asyncio
    async def test_memory_timeline(self, client):
        """Test GET /v1/memory/timeline."""
        timeline = await client.memory.timeline(hours=24, limit=20)
        assert isinstance(timeline.memories, list)
        assert len(timeline.memories) <= 20
        assert timeline.total >= 0
        assert timeline.buckets

    # ========== System Tests (6 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_system_health(self, unauthenticated_client):
        """Test GET /v1/system/health (no auth required)."""
        health = await unauthenticated_client.system.health()
        assert health.status in ["healthy", "degraded", "critical", "initializing"]
        assert health.version
        assert health.uptime_seconds >= 0
        assert health.services
    
    @pytest.mark.asyncio
    async def test_system_time(self, client):
        """Test GET /v1/system/time."""
        time_info = await client.system.time()
        assert time_info.system_time
        assert time_info.agent_time
        assert time_info.uptime_seconds >= 0
        assert time_info.time_sync
    
    @pytest.mark.asyncio
    async def test_system_resources(self, client):
        """Test GET /v1/system/resources."""
        resources = await client.system.resources()
        assert resources.current_usage
        assert resources.limits
        assert resources.health_status in ["healthy", "warning", "critical"]
    
    @pytest.mark.asyncio
    async def test_system_services(self, client):
        """Test GET /v1/system/services."""
        services = await client.system.services()
        assert services.services
        assert services.total_services >= 16  # At least 16 services should be running
        assert services.healthy_services <= services.total_services
    
    @pytest.mark.asyncio
    async def test_system_runtime_control(self, client):
        """Test POST /v1/system/runtime/{action}."""
        # Test pause
        result = await client.system.runtime_control("pause", reason="Test pause")
        assert result.success
        assert result.processor_state
        
        # Test resume
        result = await client.system.runtime_control("resume", reason="Test resume")
        assert result.success
        
        # Test state
        result = await client.system.runtime_control("state")
        assert result.success
        assert result.processor_state
    
    @pytest.mark.asyncio
    async def test_system_shutdown(self, client):
        """Test POST /v1/system/shutdown."""
        # Don't actually shutdown during tests
        with pytest.raises(Exception):
            # This should fail because we don't confirm
            await client.system.shutdown("Test shutdown", confirm=False)

    # ========== Configuration Tests (3 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_config_get_all(self, client):
        """Test GET /v1/config."""
        config = await client.config.get_all()
        assert isinstance(config, dict)
        # Should have some config keys
        assert len(config) > 0
    
    @pytest.mark.asyncio
    async def test_config_get_key(self, client):
        """Test GET /v1/config/{key}."""
        # Try to get a known config key
        try:
            value = await client.config.get("agent.name")
            assert value
        except CIRISAPIError as e:
            # Key might not exist (404), which is OK
            if e.status_code != 404:
                raise
    
    @pytest.mark.asyncio
    async def test_config_set_key(self, client):
        """Test PUT /v1/config/{key}."""
        test_key = f"test.key.{datetime.now().timestamp()}"
        test_value = "test_value"
        
        # Set the config
        await client.config.set(test_key, test_value)
        
        # Verify it was set
        value = await client.config.get(test_key)
        assert value == test_value

    # ========== Telemetry Tests (5 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_telemetry_overview(self, client):
        """Test GET /v1/telemetry/overview."""
        overview = await client.telemetry.overview()
        assert overview.uptime_seconds >= 0
        assert overview.cognitive_state
        assert hasattr(overview, 'messages_processed_24h')
        assert hasattr(overview, 'healthy_services')
    
    @pytest.mark.asyncio
    async def test_telemetry_metrics(self, client):
        """Test GET /v1/telemetry/metrics."""
        metrics = await client.telemetry.metrics()
        assert isinstance(metrics.metrics, list)
    
    @pytest.mark.asyncio
    async def test_telemetry_metric_detail(self, client):
        """Test GET /v1/telemetry/metrics/{name}."""
        # First get available metrics
        metrics = await client.telemetry.metrics()
        if metrics.metrics:
            # Use the first available metric
            metric_name = metrics.metrics[0].name
            detail = await client.telemetry.metric_detail(metric_name)
            assert detail.metric_name == metric_name
            assert hasattr(detail, 'current')
            assert hasattr(detail, 'unit')
        else:
            # No metrics available, skip test
            pytest.skip("No metrics available to test")
    
    @pytest.mark.asyncio
    async def test_telemetry_resources(self, client):
        """Test GET /v1/telemetry/resources."""
        resources = await client.telemetry.resources()
        assert resources.current
        assert resources.limits
        assert resources.health
    
    @pytest.mark.asyncio
    async def test_telemetry_resources_history(self, client):
        """Test GET /v1/telemetry/resources/history."""
        history = await client.telemetry.resources_history(hours=1)
        assert history.period
        assert isinstance(history.cpu, (list, dict))
        assert isinstance(history.memory, (list, dict))

    # ========== Audit Tests (5 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_audit_entries(self, client):
        """Test GET /v1/audit/entries."""
        entries = await client.audit.entries(limit=20)
        assert isinstance(entries.entries, list)
        assert len(entries.entries) <= 20
        assert hasattr(entries, 'has_more')
    
    @pytest.mark.asyncio
    async def test_audit_entry_detail(self, client):
        """Test GET /v1/audit/entries/{entry_id}."""
        # First get some entries
        entries = await client.audit.entries(limit=1)
        if entries.entries:
            entry_id = entries.entries[0].id
            detail = await client.audit.entry_detail(entry_id)
            assert detail.entry.id == entry_id
    
    @pytest.mark.asyncio
    async def test_audit_search(self, client):
        """Test POST /v1/audit/search."""
        results = await client.audit.search(
            search_text="test",
            limit=10
        )
        assert isinstance(results.entries, list)
        assert len(results.entries) <= 10
    
    @pytest.mark.asyncio
    async def test_audit_export(self, client):
        """Test POST /v1/audit/export."""
        export = await client.audit.export(
            format="jsonl",
            start_date=datetime.now(timezone.utc) - timedelta(days=1)
        )
        assert export.format == "jsonl"
        assert export.total_entries >= 0
    
    @pytest.mark.asyncio
    async def test_audit_verify(self, client):
        """Test POST /v1/audit/verify/{entry_id}."""
        # First get an entry
        entries = await client.audit.entries(limit=1)
        if entries.entries:
            entry_id = entries.entries[0].id
            report = await client.audit.verify(entry_id)
            assert hasattr(report, 'verified')

    # ========== Wise Authority Tests (2 endpoints) ==========
    
    @pytest.mark.asyncio
    async def test_wa_status(self, client):
        """Test GET /v1/wa/status."""
        status = await client.wa.status()
        assert isinstance(status.service_healthy, bool)
        assert status.active_was >= 0
        assert status.pending_deferrals >= 0
    
    @pytest.mark.asyncio
    async def test_wa_guidance(self, client):
        """Test POST /v1/wa/guidance."""
        guidance = await client.wa.guidance(
            topic="Should I implement this feature?",
            context="Testing WA guidance endpoint"
        )
        assert guidance.guidance
        assert guidance.wa_id
        assert 0 <= guidance.confidence <= 1

    # ========== Emergency Tests (1 endpoint) ==========
    
    @pytest.mark.asyncio
    async def test_emergency_shutdown_invalid(self, unauthenticated_client):
        """Test POST /emergency/shutdown with invalid signature."""
        # Skip this test as it requires cryptography module and valid keys
        pytest.skip("Emergency shutdown requires cryptography module and Ed25519 keys")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])