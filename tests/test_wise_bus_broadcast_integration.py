"""
Integration test for wise bus deferral broadcasting.

Tests that deferrals are broadcast to all registered wise authority services
including both core WA service and adapter-provided WA services.
"""

import logging
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from ciris_engine.logic.buses.wise_bus import WiseBus
from ciris_engine.logic.registries.base import Priority, ServiceRegistry
from ciris_engine.logic.services.governance.wise_authority import WiseAuthorityService
from ciris_engine.logic.services.lifecycle.time import TimeService
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.services.authority_core import DeferralRequest
from ciris_engine.schemas.services.context import DeferralContext

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_deferral_broadcast_with_real_services():
    """Test that deferrals are broadcast to both core and adapter WA services."""
    # Create real services
    time_service = TimeService()
    mock_auth_service = Mock()

    # Create core WA service
    core_wa_service = WiseAuthorityService(
        time_service=time_service,
        auth_service=mock_auth_service,
        db_path=":memory:",  # Use in-memory database for testing
    )

    # Mock the send_deferral method to track calls
    core_wa_service.send_deferral = AsyncMock(return_value="core_defer_123")

    # Create mock Discord adapter WA service
    discord_wa_service = Mock()
    discord_wa_service.send_deferral = AsyncMock(return_value="discord_defer_456")
    discord_caps = Mock()
    discord_caps.actions = {"send_deferral", "fetch_guidance"}
    discord_wa_service.get_capabilities = Mock(return_value=discord_caps)

    # Create service registry
    registry = ServiceRegistry()

    # Register both services
    registry.register_service(
        service_type=ServiceType.WISE_AUTHORITY,
        provider=core_wa_service,
        priority=Priority.NORMAL,
        capabilities=["send_deferral", "fetch_guidance"],
    )

    registry.register_service(
        service_type=ServiceType.WISE_AUTHORITY,
        provider=discord_wa_service,
        priority=Priority.HIGH,
        capabilities=["send_deferral", "fetch_guidance"],
    )

    # Create wise bus
    wise_bus = WiseBus(service_registry=registry, time_service=time_service)

    # Create deferral context
    context = DeferralContext(
        thought_id="thought_integration_123",
        task_id="task_integration_456",
        reason="Integration test deferral",
        defer_until=time_service.now() + timedelta(hours=2),
        priority="high",
        metadata={"test": "integration", "source": "test_suite"},
    )

    # Send deferral
    result = await wise_bus.send_deferral(context=context, handler_name="TestIntegrationHandler")

    # Verify results
    assert result is True

    # Both services should have been called
    core_wa_service.send_deferral.assert_called_once()
    discord_wa_service.send_deferral.assert_called_once()

    # Verify the deferral request content
    core_call = core_wa_service.send_deferral.call_args[0][0]
    discord_call = discord_wa_service.send_deferral.call_args[0][0]

    assert isinstance(core_call, DeferralRequest)
    assert isinstance(discord_call, DeferralRequest)

    assert core_call.thought_id == discord_call.thought_id == "thought_integration_123"
    assert core_call.task_id == discord_call.task_id == "task_integration_456"
    assert core_call.reason == discord_call.reason == "Integration test deferral"
    assert core_call.context == discord_call.context == {"test": "integration", "source": "test_suite"}


@pytest.mark.asyncio
async def test_service_registry_returns_all_wa_services():
    """Test that service registry correctly returns all WA services."""
    # Create services
    time_service = TimeService()

    # Create multiple WA services
    service1 = Mock()
    service1.get_capabilities = Mock(return_value=Mock(actions={"send_deferral"}))

    service2 = Mock()
    service2.get_capabilities = Mock(return_value=Mock(actions={"send_deferral", "fetch_guidance"}))

    service3 = Mock()
    service3.get_capabilities = Mock(return_value=Mock(actions={"fetch_guidance"}))  # No send_deferral

    # Create registry and register services
    registry = ServiceRegistry()

    registry.register_service(ServiceType.WISE_AUTHORITY, service1, Priority.LOW, ["send_deferral"])
    registry.register_service(
        ServiceType.WISE_AUTHORITY, service2, Priority.NORMAL, ["send_deferral", "fetch_guidance"]
    )
    registry.register_service(ServiceType.WISE_AUTHORITY, service3, Priority.HIGH, ["fetch_guidance"])

    # Get all WA services
    all_services = registry.get_services_by_type(ServiceType.WISE_AUTHORITY)

    # Should return all 3 services
    assert len(all_services) == 3
    assert service1 in all_services
    assert service2 in all_services
    assert service3 in all_services

    # Now test WiseBus filtering for send_deferral capability
    wise_bus = WiseBus(service_registry=registry, time_service=time_service)

    # Mock send_deferral on services that support it
    service1.send_deferral = AsyncMock(return_value="defer1")
    service2.send_deferral = AsyncMock(return_value="defer2")

    context = DeferralContext(
        thought_id="thought_filter_test",
        task_id="task_filter_test",
        reason="Test capability filtering",
        defer_until=None,
        priority="medium",
        metadata={},
    )

    # Send deferral - should only go to service1 and service2
    result = await wise_bus.send_deferral(context, "TestHandler")

    assert result is True
    service1.send_deferral.assert_called_once()
    service2.send_deferral.assert_called_once()
    # service3 should NOT be called (no send_deferral capability)
    assert not hasattr(service3, "send_deferral") or not service3.send_deferral.called


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
