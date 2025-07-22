"""
Tests for WiseBus deferral functionality.

Tests the message bus integration for deferrals, including
proper context transformation and error handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Optional

from ciris_engine.logic.buses.wise_bus import WiseBus
from ciris_engine.schemas.services.context import DeferralContext, GuidanceContext
from ciris_engine.schemas.services.authority_core import (
    DeferralRequest, DeferralResponse, WARole
)
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.protocols.services import WiseAuthorityService


class MockTimeService:
    """Mock time service for testing."""
    def __init__(self, now_time: Optional[datetime] = None):
        self._now = now_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._now


class MockWiseAuthorityService:
    """Mock wise authority service implementing the protocol."""

    def __init__(self):
        self.send_deferral = AsyncMock(return_value="defer_id_123")
        self.fetch_guidance = AsyncMock(return_value="Test guidance response")
        # get_capabilities should return an object with actions attribute
        capabilities = Mock()
        capabilities.actions = {"send_deferral", "fetch_guidance"}
        self.get_capabilities = Mock(return_value=capabilities)
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.health_check = AsyncMock(return_value={"status": "healthy"})


class TestWiseBusDeferrals:
    """Test suite for WiseBus deferral operations."""

    @pytest.fixture
    def mock_time_service(self):
        """Provide a mock time service."""
        return MockTimeService()

    @pytest.fixture
    def mock_wise_service(self):
        """Provide a mock wise authority service."""
        return MockWiseAuthorityService()

    @pytest.fixture
    def mock_service_registry(self, mock_wise_service):
        """Mock service registry that returns our WA service."""
        registry = Mock()
        registry.get_service = AsyncMock(return_value=mock_wise_service)
        # WiseBus now uses get_services_by_type for broadcasting
        registry.get_services_by_type = Mock(return_value=[mock_wise_service])
        return registry

    @pytest.fixture
    def wise_bus(self, mock_service_registry, mock_time_service):
        """Create a WiseBus instance."""
        return WiseBus(mock_service_registry, mock_time_service)

    @pytest.mark.asyncio
    async def test_send_deferral_success(
        self,
        wise_bus,
        mock_wise_service,
        mock_time_service
    ):
        """Test successful deferral submission through bus."""
        # Arrange
        context = DeferralContext(
            thought_id="thought_123",
            task_id="task_456",
            reason="Requires human review",
            defer_until=mock_time_service.now() + timedelta(hours=2),
            priority="high",
            metadata={
                "context": "sensitive_content",
                "user_id": "user_789"
            }
        )

        # Act
        result = await wise_bus.send_deferral(
            context=context,
            handler_name="TestHandler"
        )

        # Assert
        assert result is True
        mock_wise_service.send_deferral.assert_called_once()

        # Verify DeferralRequest was created correctly
        call_args = mock_wise_service.send_deferral.call_args
        deferral_request = call_args[0][0]

        assert isinstance(deferral_request, DeferralRequest)
        assert deferral_request.thought_id == context.thought_id
        assert deferral_request.task_id == context.task_id
        assert deferral_request.reason == context.reason
        assert deferral_request.defer_until == context.defer_until
        assert deferral_request.context == context.metadata

    @pytest.mark.asyncio
    async def test_send_deferral_with_string_defer_until(
        self,
        wise_bus,
        mock_wise_service,
        mock_time_service
    ):
        """Test deferral with string timestamp that needs parsing."""
        # Arrange
        defer_time_str = "2025-01-20T15:00:00Z"
        context = DeferralContext(
            thought_id="thought_123",
            task_id="task_456",
            reason="Scheduled review",
            defer_until=defer_time_str,  # String instead of datetime
            priority="medium",
            metadata={}
        )

        # Act
        result = await wise_bus.send_deferral(
            context=context,
            handler_name="TestHandler"
        )

        # Assert
        assert result is True

        call_args = mock_wise_service.send_deferral.call_args
        deferral_request = call_args[0][0]

        # Should have parsed the string to datetime
        assert isinstance(deferral_request.defer_until, datetime)
        expected_time = datetime.fromisoformat("2025-01-20T15:00:00+00:00")
        assert deferral_request.defer_until == expected_time

    @pytest.mark.asyncio
    async def test_send_deferral_no_defer_until(
        self,
        wise_bus,
        mock_wise_service,
        mock_time_service
    ):
        """Test deferral without defer_until defaults to 1 hour."""
        # Arrange
        context = DeferralContext(
            thought_id="thought_123",
            task_id="task_456",
            reason="General review needed",
            defer_until=None,
            priority="low",
            metadata={}
        )

        # Act
        result = await wise_bus.send_deferral(
            context=context,
            handler_name="TestHandler"
        )

        # Assert
        assert result is True

        call_args = mock_wise_service.send_deferral.call_args
        deferral_request = call_args[0][0]

        # Should default to now + 1 hour
        expected_time = mock_time_service.now() + timedelta(hours=1)
        time_diff = abs((deferral_request.defer_until - expected_time).total_seconds())
        assert time_diff < 1  # Within 1 second tolerance

    @pytest.mark.asyncio
    async def test_send_deferral_service_not_available(
        self,
        wise_bus,
        mock_service_registry
    ):
        """Test deferral when no WA service is available."""
        # Arrange
        mock_service_registry.get_service.return_value = None
        mock_service_registry.get_services_by_type.return_value = []

        context = DeferralContext(
            thought_id="thought_123",
            task_id="task_456",
            reason="Test deferral",
            defer_until=None,
            priority="medium",
            metadata={}
        )

        # Act
        result = await wise_bus.send_deferral(
            context=context,
            handler_name="TestHandler"
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_send_deferral_service_exception(
        self,
        wise_bus,
        mock_wise_service
    ):
        """Test deferral when WA service throws exception."""
        # Arrange
        mock_wise_service.send_deferral.side_effect = Exception("Service error")

        context = DeferralContext(
            thought_id="thought_123",
            task_id="task_456",
            reason="Test deferral",
            defer_until=None,
            priority="high",
            metadata={}
        )

        # Act
        result = await wise_bus.send_deferral(
            context=context,
            handler_name="TestHandler"
        )

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_fetch_guidance_success(
        self,
        wise_bus,
        mock_wise_service
    ):
        """Test successful guidance fetch through bus."""
        # Arrange
        context = GuidanceContext(
            thought_id="thought_123",
            task_id="task_456",
            question="Should I proceed with this medical recommendation?",
            ethical_considerations=[
                "Patient safety",
                "Medical ethics",
                "Informed consent"
            ],
            domain_context={
                "domain": "healthcare",
                "risk_level": "high"
            }
        )

        # Act
        result = await wise_bus.fetch_guidance(
            context=context,
            handler_name="MedicalHandler"
        )

        # Assert
        assert result == "Test guidance response"
        mock_wise_service.fetch_guidance.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_fetch_guidance_no_service(
        self,
        wise_bus,
        mock_service_registry
    ):
        """Test guidance fetch when no service available."""
        # Arrange
        mock_service_registry.get_service.return_value = None

        context = GuidanceContext(
            thought_id="thought_123",
            task_id="task_456",
            question="Test question",
            ethical_considerations=[],
            domain_context={}
        )

        # Act
        result = await wise_bus.fetch_guidance(
            context=context,
            handler_name="TestHandler"
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_request_review(
        self,
        wise_bus,
        mock_wise_service
    ):
        """Test the request_review convenience method."""
        # Arrange
        review_data = {
            "identity_variance": 0.85,
            "expected": "helpful_assistant",
            "actual": "cautious_advisor",
            "context": "risk_assessment"
        }

        # Act
        result = await wise_bus.request_review(
            review_type="identity_variance",
            review_data=review_data,
            handler_name="IdentityMonitor"
        )

        # Assert
        assert result is True

        # Verify deferral was created for review
        call_args = mock_wise_service.send_deferral.call_args
        deferral_request = call_args[0][0]

        assert deferral_request.reason == "Review requested: identity_variance"
        assert "review_data" in deferral_request.context
        assert "IdentityMonitor" in deferral_request.context["handler_name"]

    @pytest.mark.asyncio
    async def test_bus_capability_filtering(
        self,
        wise_bus,
        mock_service_registry,
        mock_wise_service
    ):
        """Test that bus properly filters services by capabilities."""
        # Arrange
        # Create services with different capabilities
        service_without_defer = Mock()
        capabilities_without_defer = Mock()
        capabilities_without_defer.actions = {"fetch_guidance"}
        service_without_defer.get_capabilities = Mock(return_value=capabilities_without_defer)

        service_with_defer = mock_wise_service

        # Registry returns different services based on handler
        async def get_service_by_handler(handler, service_type, **kwargs):
            required_capabilities = kwargs.get('required_capabilities', [])

            if handler == "HandlerA":
                service = service_without_defer
            else:
                service = service_with_defer

            # Check if service has required capabilities
            if required_capabilities:
                service_caps = service.get_capabilities()
                if not all(cap in service_caps.actions for cap in required_capabilities):
                    return None

            return service

        mock_service_registry.get_service.side_effect = get_service_by_handler

        context = DeferralContext(
            thought_id="thought_123",
            task_id="task_456",
            reason="Test",
            defer_until=None,
            priority="medium",
            metadata={}
        )

        # Act & Assert
        # Handler A's service lacks send_deferral capability
        result_a = await wise_bus.get_service(
            handler_name="HandlerA",
            required_capabilities=["send_deferral"]
        )
        assert result_a is None

        # Handler B's service has the capability
        result_b = await wise_bus.get_service(
            handler_name="HandlerB",
            required_capabilities=["send_deferral"]
        )
        assert result_b == service_with_defer

    @pytest.mark.asyncio
    async def test_concurrent_deferral_requests(
        self,
        wise_bus,
        mock_wise_service
    ):
        """Test handling multiple concurrent deferral requests."""
        # Arrange
        contexts = [
            DeferralContext(
                thought_id=f"thought_{i}",
                task_id=f"task_{i}",
                reason=f"Reason {i}",
                defer_until=None,
                priority="medium",
                metadata={"index": str(i)}
            )
            for i in range(5)
        ]

        # Act
        import asyncio
        results = await asyncio.gather(*[
            wise_bus.send_deferral(ctx, f"Handler_{i}")
            for i, ctx in enumerate(contexts)
        ])

        # Assert
        assert all(results)
        assert mock_wise_service.send_deferral.call_count == 5

        # Verify each call had unique context
        thought_ids = set()
        for call in mock_wise_service.send_deferral.call_args_list:
            req = call[0][0]
            thought_ids.add(req.thought_id)

        assert len(thought_ids) == 5

    @pytest.mark.asyncio
    async def test_deferral_broadcast_to_multiple_services(
        self,
        wise_bus,
        mock_service_registry,
        mock_time_service
    ):
        """Test that deferrals are broadcast to ALL wise authority services."""
        # Arrange - Create multiple WA services (Discord and API)
        discord_wa_service = MockWiseAuthorityService()
        api_wa_service = MockWiseAuthorityService()
        
        # Both services should support send_deferral
        discord_caps = Mock()
        discord_caps.actions = {"send_deferral", "fetch_guidance", "check_permission"}
        discord_wa_service.get_capabilities = Mock(return_value=discord_caps)
        
        api_caps = Mock()
        api_caps.actions = {"send_deferral", "fetch_guidance", "list_permissions"}
        api_wa_service.get_capabilities = Mock(return_value=api_caps)
        
        # Registry returns both services
        mock_service_registry.get_services_by_type.return_value = [
            discord_wa_service,
            api_wa_service
        ]
        
        context = DeferralContext(
            thought_id="thought_broadcast_123",
            task_id="task_broadcast_456",
            reason="Test broadcast to all WA services",
            defer_until=mock_time_service.now() + timedelta(hours=1),
            priority="high",
            metadata={"test": "broadcast"}
        )
        
        # Act
        result = await wise_bus.send_deferral(
            context=context,
            handler_name="TestBroadcastHandler"
        )
        
        # Assert
        assert result is True  # Should succeed if at least one service processed it
        
        # Both services should have received the deferral
        discord_wa_service.send_deferral.assert_called_once()
        api_wa_service.send_deferral.assert_called_once()
        
        # Verify both got the same deferral request
        discord_call = discord_wa_service.send_deferral.call_args[0][0]
        api_call = api_wa_service.send_deferral.call_args[0][0]
        
        assert discord_call.thought_id == api_call.thought_id == "thought_broadcast_123"
        assert discord_call.task_id == api_call.task_id == "task_broadcast_456"
        assert discord_call.reason == api_call.reason == "Test broadcast to all WA services"

    @pytest.mark.asyncio
    async def test_deferral_partial_failure(
        self,
        wise_bus,
        mock_service_registry,
        mock_time_service
    ):
        """Test that deferral succeeds if at least one WA service processes it."""
        # Arrange - Create two services, one will fail
        working_service = MockWiseAuthorityService()
        failing_service = MockWiseAuthorityService()
        
        # Set up capabilities
        caps = Mock()
        caps.actions = {"send_deferral"}
        working_service.get_capabilities = Mock(return_value=caps)
        failing_service.get_capabilities = Mock(return_value=caps)
        
        # Make one service fail
        failing_service.send_deferral.side_effect = Exception("Service unavailable")
        
        mock_service_registry.get_services_by_type.return_value = [
            failing_service,
            working_service
        ]
        
        context = DeferralContext(
            thought_id="thought_partial_123",
            task_id="task_partial_456", 
            reason="Test partial failure",
            defer_until=None,
            priority="medium",
            metadata={}
        )
        
        # Act
        result = await wise_bus.send_deferral(
            context=context,
            handler_name="TestPartialHandler"
        )
        
        # Assert
        assert result is True  # Should succeed because one service worked
        working_service.send_deferral.assert_called_once()
        failing_service.send_deferral.assert_called_once()


class TestWiseBusErrorHandling:
    """Test error handling scenarios in WiseBus."""

    @pytest.fixture
    def mock_time_service(self):
        """Provide a mock time service."""
        return MockTimeService()

    @pytest.fixture
    def wise_bus(self):
        """Create WiseBus with minimal mocking."""
        mock_registry = Mock()
        mock_registry.get_services_by_type = Mock(return_value=[])
        mock_time = MockTimeService()
        return WiseBus(mock_registry, mock_time)

    @pytest.mark.asyncio
    async def test_invalid_defer_until_format(
        self,
        wise_bus,
        mock_time_service
    ):
        """Test handling of invalid defer_until timestamp in Pydantic validation."""
        # Arrange
        mock_service = MockWiseAuthorityService()
        wise_bus.service_registry.get_service = AsyncMock(return_value=mock_service)
        wise_bus.service_registry.get_services_by_type = Mock(return_value=[mock_service])

        # Since DeferralContext expects datetime or None, passing an invalid string
        # will raise a Pydantic ValidationError at model creation time
        from pydantic import ValidationError

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            context = DeferralContext(
                thought_id="thought_123",
                task_id="task_456",
                reason="Test",
                defer_until="invalid-timestamp",  # Invalid format - will fail validation
                priority="medium",
                metadata={}
            )

        # Verify the validation error is about the defer_until field
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('defer_until',) for error in errors)

        # Now test that a properly formed context works
        valid_context = DeferralContext(
            thought_id="thought_123",
            task_id="task_456",
            reason="Test",
            defer_until=mock_time_service.now(),  # Valid datetime
            priority="medium",
            metadata={}
        )

        result = await wise_bus.send_deferral(valid_context, "TestHandler")
        assert result is True

    @pytest.mark.asyncio
    async def test_process_message_warning(
        self,
        wise_bus,
        caplog
    ):
        """Test that async message processing logs warning."""
        # Arrange
        from ciris_engine.logic.buses.base_bus import BusMessage
        from datetime import datetime, timezone
        message = BusMessage(
            id="test_msg_001",
            handler_name="TestHandler",
            timestamp=datetime.now(timezone.utc),
            metadata={"test": "data"}
        )

        # Act
        await wise_bus._process_message(message)

        # Assert
        assert "should be synchronous" in caplog.text
        assert "got queued message" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
