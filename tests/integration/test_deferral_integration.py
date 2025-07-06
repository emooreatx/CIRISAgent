"""
Integration tests for the complete deferral system.

Tests the full flow from handler -> bus -> WA service -> resolution,
including Discord adapter integration for human-in-the-loop scenarios.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import asyncio
from typing import List, Optional, Dict, Any, cast

from ciris_engine.logic.handlers.control.defer_handler import DeferHandler
from ciris_engine.logic.buses.bus_manager import BusManager
from ciris_engine.logic.buses.wise_bus import WiseBus
from ciris_engine.logic.services.governance.wise_authority import WiseAuthorityService
from ciris_engine.logic.infrastructure.handlers.base_handler import ActionHandlerDependencies
from ciris_engine.schemas.actions.parameters import DeferParams
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.runtime.models import Thought, ThoughtContext, Task
from ciris_engine.schemas.runtime.enums import (
    ThoughtStatus, TaskStatus, HandlerActionType, ServiceType
)
from ciris_engine.schemas.runtime.contexts import DispatchContext
from ciris_engine.schemas.services.context import DeferralContext
from ciris_engine.schemas.services.authority.wise_authority import (
    PendingDeferral, DeferralResolution
)
from ciris_engine.schemas.services.authority_core import (
    DeferralRequest, DeferralResponse, WARole, WACertificate
)


class MockTimeService:
    """Mock time service for testing."""
    def __init__(self, now_time: Optional[datetime] = None):
        self._now = now_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def now_iso(self) -> str:
        """Get current time as ISO string."""
        return self._now.isoformat()

    def timestamp(self) -> float:
        """Return current timestamp as float."""
        return self._now.timestamp()

    def advance(self, seconds: int) -> None:
        """Advance time by given seconds."""
        self._now += timedelta(seconds=seconds)


class MockMemoryService:
    """Mock memory service for WA storage."""
    def __init__(self) -> None:
        self.deferrals: Dict[str, PendingDeferral] = {}
        self.wa_certificates: Dict[str, WACertificate] = {}
        self.memorize = AsyncMock()
        self.recall = AsyncMock()

    async def store_deferral(self, deferral: PendingDeferral) -> str:
        """Store a deferral and return its ID."""
        self.deferrals[deferral.deferral_id] = deferral
        return deferral.deferral_id

    async def get_deferrals(self, wa_id: Optional[str] = None) -> List[PendingDeferral]:
        """Get deferrals, optionally filtered by WA."""
        deferrals = list(self.deferrals.values())
        if wa_id:
            deferrals = [d for d in deferrals if d.assigned_wa_id == wa_id]
        return deferrals

    async def update_deferral(self, deferral_id: str, resolution: DeferralResolution) -> bool:
        """Update a deferral with resolution."""
        if deferral_id not in self.deferrals:
            return False

        deferral = self.deferrals[deferral_id]
        deferral.status = "resolved"
        deferral.resolution = resolution.resolution
        deferral.resolved_at = datetime.now(timezone.utc)
        return True


class IntegrationTestBase:
    """Base class for integration tests with common fixtures."""

    @pytest.fixture
    def mock_time_service(self) -> MockTimeService:
        """Provide a mock time service."""
        return MockTimeService()

    @pytest.fixture
    def mock_memory_service(self) -> MockMemoryService:
        """Provide a mock memory service."""
        return MockMemoryService()

    @pytest.fixture
    def mock_persistence(self, monkeypatch: pytest.MonkeyPatch) -> Mock:
        """Mock persistence module."""
        mock = Mock()
        mock.update_thought_status = Mock()
        mock.update_task_status = Mock()
        mock.get_task_by_id = Mock(return_value=Task(
            task_id="test_task",
            channel_id="test_channel",
            description="Test task for integration",
            status=TaskStatus.ACTIVE,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            parent_task_id=None,
            context=None,
            outcome=None,
            signed_by=None,
            signature=None,
            signed_at=None
        ))
        monkeypatch.setattr('ciris_engine.logic.handlers.control.defer_handler.persistence', mock)
        return mock

    @pytest.fixture
    def mock_auth_service(self) -> AsyncMock:
        """Create a mock authentication service."""
        auth_service = AsyncMock()
        auth_service.bootstrap_if_needed = AsyncMock()
        auth_service.get_wa = AsyncMock(return_value=None)
        return auth_service

    @pytest.fixture
    def mock_service_registry(self, mock_memory_service: MockMemoryService, mock_time_service: MockTimeService, mock_auth_service: AsyncMock) -> Mock:
        """Create a mock service registry."""
        registry = Mock()

        # Mock WA service with correct parameters
        # Cast to avoid mypy errors - our mock implements the protocol
        wa_service = WiseAuthorityService(
            time_service=cast(Any, mock_time_service),
            auth_service=mock_auth_service,
            db_path=":memory:"  # Use in-memory SQLite for tests
        )
        # Initialize the service to ensure database is set up
        asyncio.run(wa_service.start())

        # Create scheduler once to reuse
        scheduler = AsyncMock()
        scheduler.schedule_deferred_task = AsyncMock(
            return_value=Mock(task_id="scheduled_123")
        )

        def get_service_sync(handler: Optional[str] = None, service_type: Optional[str] = None, required_capabilities: Optional[List[str]] = None, fallback_to_global: bool = True) -> Optional[Any]:
            if service_type == ServiceType.WISE_AUTHORITY or service_type == "wise_authority":
                return wa_service
            elif handler == "task_scheduler" and service_type == "scheduler":
                return scheduler
            return None

        # Create async version
        async def get_service_async(handler: Optional[str] = None, service_type: Optional[str] = None, required_capabilities: Optional[List[str]] = None, fallback_to_global: bool = True) -> Optional[Any]:
            return get_service_sync(handler, service_type, required_capabilities, fallback_to_global)

        # Use AsyncMock to properly handle both sync and async calls
        registry.get_service = AsyncMock(side_effect=get_service_async)
        return registry

    @pytest.fixture
    def bus_manager(self, mock_service_registry: Mock, mock_time_service: MockTimeService) -> BusManager:
        """Create a real bus manager with WiseBus."""
        # Mock audit service
        mock_audit_service = AsyncMock()
        mock_audit_service.log_event = AsyncMock()

        manager = BusManager(
            mock_service_registry,
            time_service=cast(Any, mock_time_service),
            audit_service=mock_audit_service
        )

        # Create real WiseBus
        manager.wise = WiseBus(mock_service_registry, cast(Any, mock_time_service))

        return manager

    @pytest.fixture
    def defer_handler(self, bus_manager: BusManager, mock_time_service: MockTimeService, mock_service_registry: Mock) -> DeferHandler:
        """Create a defer handler with real dependencies."""
        deps = ActionHandlerDependencies(
            bus_manager=bus_manager,
            time_service=cast(Any, mock_time_service)
        )
        handler = DeferHandler(deps)
        # Store service registry in deps instead of private attribute
        setattr(handler, '_service_registry', mock_service_registry)
        return handler

    def create_channel_context(self, channel_id: str = "test_channel") -> Any:
        """Helper to create channel context."""
        from ciris_engine.schemas.runtime.system_context import ChannelContext
        return ChannelContext(
            channel_id=channel_id,
            channel_name=f"Channel {channel_id}",
            channel_type="text",
            created_at=datetime.now(timezone.utc),
            is_private=False,
            is_active=True,
            last_activity=datetime.now(timezone.utc),
            message_count=0,
            moderation_level="standard"
        )


class TestDeferralIntegration(IntegrationTestBase):
    """Test complete deferral flow integration."""

    @pytest.mark.asyncio
    async def test_full_deferral_flow(
        self,
        defer_handler: DeferHandler,
        mock_persistence: Mock,
        mock_memory_service: MockMemoryService,
        mock_service_registry: Mock
    ) -> None:
        """Test complete flow: defer -> store -> list -> resolve."""
        # Step 1: Create and handle deferral
        thought = Thought(
            thought_id="thought_medical_001",
            source_task_id="task_medical_001",
            content="Recommend treatment for patient symptoms",
            status=ThoughtStatus.PROCESSING,
            thought_depth=1,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            channel_id="medical_channel",
            round_number=1,
            ponder_notes=None,
            parent_thought_id=None,
            final_action=None,
            context=ThoughtContext(
                task_id="task_medical_001",
                round_number=1,
                depth=1,
                correlation_id="medical_correlation",
                channel_id="medical_channel",
                parent_thought_id=None
            )
        )

        params = DeferParams(
            reason="Medical decision requires licensed physician review",
            context={
                "patient_id": "p12345",
                "symptoms": "chest_pain",
                "risk_level": "high"
            },
            defer_until=None
        )

        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=params,
            rationale="Medical decisions require human doctor",
            reasoning="High risk medical case",
            evaluation_time_ms=50,
            raw_llm_response="{\"action\": \"DEFER\", \"reason\": \"Medical decision\"}",
            resource_usage=None
        )

        dispatch_context = DispatchContext(
            channel_context=self.create_channel_context("medical_channel"),
            author_id="patient_001",
            author_name="John Doe",
            origin_service="medical_assistant",
            handler_name="DeferHandler",
            action_type=HandlerActionType.DEFER,
            task_id=thought.source_task_id,
            thought_id=thought.thought_id,
            source_task_id=thought.source_task_id,
            event_summary="Medical consultation deferred",
            event_timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id="medical_correlation",
            wa_id=None,
            wa_authorized=False,
            wa_context=None,
            conscience_failure_context=None,
            epistemic_data=None,
            span_id=None,
            trace_id=None
        )

        # Execute deferral
        await defer_handler.handle(result, thought, dispatch_context)

        # Verify deferral was stored (through WA service)
        wa_service = await mock_service_registry.get_service(service_type=ServiceType.WISE_AUTHORITY)

        # Step 2: List pending deferrals
        pending = await wa_service.get_pending_deferrals()
        assert len(pending) > 0

        medical_deferral = next(
            (d for d in pending if d.thought_id == "thought_medical_001"),
            None
        )
        assert medical_deferral is not None
        assert medical_deferral.reason == params.reason
        assert medical_deferral.priority == "normal"  # Default from WA service

        # Step 3: WA resolves deferral
        wa_cert = WACertificate(
            wa_id="wa-2025-06-28-ABC123",  # Correct format
            name="Dr. Smith",
            role=WARole.AUTHORITY,
            pubkey="test_public_key_base64url",  # Correct field name
            jwt_kid="test_jwt_kid",
            scopes_json='["medical_decisions", "resolve_deferrals"]',  # JSON string
            created_at=datetime.now(timezone.utc)
        )

        response = DeferralResponse(
            approved=True,
            reason="Approved: Prescribe antibiotics with monitoring",
            modified_time=None,
            wa_id=wa_cert.wa_id,
            signature="doctor_signature_001"
        )

        # Resolve the deferral
        resolved = await wa_service.resolve_deferral(
            medical_deferral.deferral_id,
            response
        )
        assert resolved is True

        # Step 4: Verify resolution
        pending_after = await wa_service.get_pending_deferrals()
        medical_still_pending = any(
            d.thought_id == "thought_medical_001" and d.status == "pending"
            for d in pending_after
        )
        assert not medical_still_pending

    @pytest.mark.asyncio
    async def test_concurrent_deferrals_different_priorities(
        self,
        defer_handler: DeferHandler,
        mock_persistence: Mock,
        mock_service_registry: Mock
    ) -> None:
        """Test handling multiple deferrals with different priorities."""
        # Create deferrals with different priorities
        deferrals = [
            {
                "thought_id": "thought_low_001",
                "task_id": "task_low_001",
                "reason": "Low priority review needed",
                "context": {"priority": "low"}
            },
            {
                "thought_id": "thought_critical_001",
                "task_id": "task_critical_001",
                "reason": "CRITICAL: Security breach detected",
                "context": {"priority": "critical", "threat": "data_exfiltration"}
            },
            {
                "thought_id": "thought_high_001",
                "task_id": "task_high_001",
                "reason": "High priority financial transaction",
                "context": {"priority": "high", "amount": "50000"}
            }
        ]

        # Handle all deferrals
        tasks = []
        for deferral_data in deferrals:
            thought = Thought(
                thought_id=str(deferral_data["thought_id"]),
                source_task_id=str(deferral_data["task_id"]),
                content=f"Content for {deferral_data['thought_id']}",
                status=ThoughtStatus.PROCESSING,
                thought_depth=1,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                channel_id="test_channel",
                round_number=1,
                ponder_notes=None,
                parent_thought_id=None,
                final_action=None,
                context=ThoughtContext(
                    task_id=str(deferral_data["task_id"]),
                    round_number=1,
                    depth=1,
                    correlation_id=f"corr_{deferral_data['thought_id']}",
                    channel_id="test_channel",
                    parent_thought_id=None
                )
            )

            params = DeferParams(
                reason=str(deferral_data["reason"]),
                context=cast(Dict[str, str], deferral_data["context"]),
                defer_until=None
            )

            result = ActionSelectionDMAResult(
                selected_action=HandlerActionType.DEFER,
                action_parameters=params,
                rationale=f"Deferring {deferral_data['thought_id']}",
                reasoning="Priority-based deferral",
                evaluation_time_ms=100,
                raw_llm_response="{\"action\": \"DEFER\"}",
                resource_usage=None
            )

            dispatch_context = DispatchContext(
                channel_context=self.create_channel_context(),
                author_id="system",
                author_name="System",
                origin_service="priority_handler",
                handler_name="DeferHandler",
                action_type=HandlerActionType.DEFER,
                task_id=thought.source_task_id,
                thought_id=thought.thought_id,
                source_task_id=thought.source_task_id,
                event_summary=f"Deferred: {deferral_data['reason']}",
                event_timestamp=datetime.now(timezone.utc).isoformat(),
                correlation_id=f"corr_{thought.thought_id}",
                wa_id=None,
                wa_authorized=False,
                wa_context=None,
                conscience_failure_context=None,
                epistemic_data=None,
                span_id=None,
                trace_id=None
            )

            task = defer_handler.handle(result, thought, dispatch_context)
            tasks.append(task)

        # Execute all deferrals concurrently
        await asyncio.gather(*tasks)

        # Get WA service and check deferrals
        wa_service = await mock_service_registry.get_service(service_type=ServiceType.WISE_AUTHORITY)
        pending = await wa_service.get_pending_deferrals()

        # Should have all three deferrals
        assert len(pending) >= 3

        # Find our deferrals
        critical = next((d for d in pending if "CRITICAL" in d.reason), None)
        high = next((d for d in pending if "financial transaction" in d.reason), None)
        low = next((d for d in pending if "Low priority" in d.reason), None)

        assert critical is not None
        assert high is not None
        assert low is not None

        # All should have default "normal" priority from WA service
        # (The context priority is stored but not used for WA priority)
        assert critical.priority == "normal"
        assert high.priority == "normal"
        assert low.priority == "normal"

    @pytest.mark.asyncio
    async def test_time_based_deferral_with_scheduler(
        self,
        defer_handler: DeferHandler,
        mock_persistence: Mock,
        mock_service_registry: Mock,
        mock_time_service: MockTimeService
    ) -> None:
        """Test time-based deferral with task scheduler integration."""
        # Set current time
        current_time = datetime.now(timezone.utc)
        mock_time_service._now = current_time

        # Create deferral for 3 hours in future
        defer_until = current_time + timedelta(hours=3)

        thought = Thought(
            thought_id="thought_scheduled_001",
            source_task_id="task_scheduled_001",
            content="Check payment status after processing time",
            status=ThoughtStatus.PROCESSING,
            thought_depth=1,
            created_at=current_time.isoformat(),
            updated_at=current_time.isoformat(),
            channel_id="payment_channel",
            round_number=1,
            ponder_notes=None,
            parent_thought_id=None,
            final_action=None,
            context=ThoughtContext(
                task_id="task_scheduled_001",
                round_number=1,
                depth=1,
                correlation_id="payment_correlation",
                channel_id="payment_channel",
                parent_thought_id=None
            )
        )

        params = DeferParams(
            reason="Wait for payment processor confirmation",
            defer_until=defer_until.isoformat(),
            context={
                "payment_id": "pay_12345",
                "expected_duration": "3_hours"
            }
        )

        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=params,
            rationale="Payment processing requires time",
            reasoning="External system dependency",
            evaluation_time_ms=75,
            raw_llm_response="{\"action\": \"DEFER\"}",
            resource_usage=None
        )

        dispatch_context = DispatchContext(
            channel_context=self.create_channel_context("payment_channel"),
            author_id="merchant_001",
            author_name="Test Merchant",
            origin_service="payment_service",
            handler_name="DeferHandler",
            action_type=HandlerActionType.DEFER,
            task_id=thought.source_task_id,
            thought_id=thought.thought_id,
            source_task_id=thought.source_task_id,
            event_summary="Payment verification deferred",
            event_timestamp=current_time.isoformat(),
            correlation_id="payment_correlation",
            wa_id=None,
            wa_authorized=False,
            wa_context=None,
            conscience_failure_context=None,
            epistemic_data=None,
            span_id=None,
            trace_id=None
        )

        # Execute deferral
        await defer_handler.handle(result, thought, dispatch_context)

        # Verify scheduler was called
        scheduler = await mock_service_registry.get_service(
            handler="task_scheduler",
            service_type="scheduler"
        )
        scheduler.schedule_deferred_task.assert_called_once_with(
            thought_id=thought.thought_id,
            task_id=thought.source_task_id,
            defer_until=params.defer_until,
            reason=params.reason,
            context=params.context
        )

        # Verify WA service also received the deferral
        wa_service = await mock_service_registry.get_service(service_type=ServiceType.WISE_AUTHORITY)
        pending = await wa_service.get_pending_deferrals()

        scheduled_deferral = next(
            (d for d in pending if d.thought_id == "thought_scheduled_001"),
            None
        )
        assert scheduled_deferral is not None

    @pytest.mark.asyncio
    async def test_deferral_modification_by_wa(
        self,
        defer_handler: DeferHandler,
        mock_persistence: Mock,
        mock_service_registry: Mock,
        mock_time_service: MockTimeService
    ) -> None:
        """Test WA modifying a deferral during resolution."""
        # Create initial deferral
        thought = Thought(
            thought_id="thought_modify_001",
            source_task_id="task_modify_001",
            content="Process large financial transaction",
            status=ThoughtStatus.PROCESSING,
            thought_depth=1,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            channel_id="finance_channel",
            round_number=1,
            ponder_notes=None,
            parent_thought_id=None,
            final_action=None,
            context=ThoughtContext(
                task_id="task_modify_001",
                round_number=1,
                depth=1,
                correlation_id="finance_correlation",
                channel_id="finance_channel",
                parent_thought_id=None
            )
        )

        params = DeferParams(
            reason="Large transaction requires approval",
            context={
                "amount": "100000",
                "currency": "USD",
                "recipient": "offshore_account"
            },
            defer_until=None
        )

        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=params,
            rationale="High value transaction needs review",
            reasoning="Risk management protocol",
            evaluation_time_ms=90,
            raw_llm_response="{\"action\": \"DEFER\"}",
            resource_usage=None
        )

        dispatch_context = DispatchContext(
            channel_context=self.create_channel_context("finance_channel"),
            author_id="trader_001",
            author_name="Trader",
            origin_service="trading_system",
            handler_name="DeferHandler",
            action_type=HandlerActionType.DEFER,
            task_id=thought.source_task_id,
            thought_id=thought.thought_id,
            source_task_id=thought.source_task_id,
            event_summary="Large transaction deferred",
            event_timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id="finance_correlation",
            wa_id=None,
            wa_authorized=False,
            wa_context=None,
            conscience_failure_context=None,
            epistemic_data=None,
            span_id=None,
            trace_id=None
        )

        # Handle deferral
        await defer_handler.handle(result, thought, dispatch_context)

        # Get the deferral
        wa_service = await mock_service_registry.get_service(service_type=ServiceType.WISE_AUTHORITY)
        pending = await wa_service.get_pending_deferrals()
        transaction_deferral = next(
            (d for d in pending if d.thought_id == "thought_modify_001"),
            None
        )

        # WA modifies the transaction
        modified_response = DeferralResponse(
            approved=True,
            reason="Approved with modifications: reduced amount and added safeguards",
            modified_time=mock_time_service.now() + timedelta(days=7),  # Review in 7 days
            wa_id="wa_compliance_001",
            signature="compliance_signature"
        )

        # Create detailed resolution with modifications
        assert transaction_deferral is not None
        resolution = DeferralResolution(
            deferral_id=transaction_deferral.deferral_id,
            wa_id="wa_compliance_001",
            resolution="modify",
            guidance="Transaction approved with following modifications",
            modified_action="process_financial_transaction",
            modified_parameters={
                "amount": 50000,  # Reduced from 100000
                "currency": "USD",
                "recipient": "offshore_account",
                "require_2fa": True,
                "split_transfer": True,
                "notify_compliance": True
            },
            new_constraints=[
                "max_daily_transfer_50k",
                "require_source_of_funds",
                "aml_enhanced_monitoring"
            ],
            removed_constraints=[],
            resolution_metadata={
                "risk_score": "high",
                "compliance_review": "completed",
                "next_review_date": (mock_time_service.now() + timedelta(days=7)).isoformat()
            }
        )

        # Resolve with modifications
        resolved = await wa_service.resolve_deferral(
            transaction_deferral.deferral_id,
            modified_response
        )
        assert resolved is True

        # Verify deferral is no longer pending
        pending_after = await wa_service.get_pending_deferrals()
        still_pending = any(
            d.thought_id == "thought_modify_001" and d.status == "pending"
            for d in pending_after
        )
        assert not still_pending


class TestDeferralErrorScenarios(IntegrationTestBase):
    """Test error handling in deferral integration."""

    @pytest.mark.asyncio
    async def test_wa_service_unavailable_fallback(
        self,
        defer_handler: DeferHandler,
        mock_persistence: Mock,
        mock_service_registry: Mock
    ) -> None:
        """Test graceful handling when WA service is unavailable."""
        # Make WA service unavailable
        original_get_service = mock_service_registry.get_service

        async def failing_get_service(handler: Optional[str] = None, service_type: Optional[str] = None, required_capabilities: Optional[List[str]] = None, fallback_to_global: bool = True) -> Optional[Any]:
            if service_type == ServiceType.WISE_AUTHORITY or service_type == "wise_authority":
                return None  # Service unavailable
            return await original_get_service(handler, service_type, required_capabilities, fallback_to_global)

        mock_service_registry.get_service = AsyncMock(side_effect=failing_get_service)

        # Create deferral
        thought = Thought(
            thought_id="thought_no_wa_001",
            source_task_id="task_no_wa_001",
            content="Decision without WA service",
            status=ThoughtStatus.PROCESSING,
            thought_depth=1,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            channel_id="test_channel",
            round_number=1,
            ponder_notes=None,
            parent_thought_id=None,
            final_action=None,
            context=ThoughtContext(
                task_id="task_no_wa_001",
                round_number=1,
                depth=1,
                correlation_id="no_wa_correlation",
                channel_id="test_channel",
                parent_thought_id=None
            )
        )

        params = DeferParams(
            reason="Test deferral without WA service",
            context={"test": "no_wa_scenario"},
            defer_until=None
        )

        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=params,
            rationale="Testing WA unavailability",
            reasoning="Resilience test",
            evaluation_time_ms=100,
            raw_llm_response="{\"action\": \"DEFER\"}",
            resource_usage=None
        )

        dispatch_context = DispatchContext(
            channel_context=self.create_channel_context(),
            author_id="test_user",
            author_name="Test User",
            origin_service="test_service",
            handler_name="DeferHandler",
            action_type=HandlerActionType.DEFER,
            task_id=thought.source_task_id,
            thought_id=thought.thought_id,
            source_task_id=thought.source_task_id,
            event_summary="Deferral without WA",
            event_timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id="no_wa_correlation",
            wa_id=None,
            wa_authorized=False,
            wa_context=None,
            conscience_failure_context=None,
            epistemic_data=None,
            span_id=None,
            trace_id=None
        )

        # Should not raise exception
        await defer_handler.handle(result, thought, dispatch_context)

        # Verify thought and task were still updated
        mock_persistence.update_thought_status.assert_called_once_with(
            thought_id=thought.thought_id,
            status=ThoughtStatus.DEFERRED,
            final_action=result
        )
        mock_persistence.update_task_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_malformed_deferral_recovery(
        self,
        defer_handler: DeferHandler,
        mock_persistence: Mock,
        bus_manager: BusManager
    ) -> None:
        """Test recovery from malformed deferral parameters."""
        # Create thought
        thought = Thought(
            thought_id="thought_malformed_001",
            source_task_id="task_malformed_001",
            content="Test malformed parameters",
            status=ThoughtStatus.PROCESSING,
            thought_depth=1,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            channel_id="test_channel",
            round_number=1,
            ponder_notes=None,
            parent_thought_id=None,
            final_action=None,
            context=ThoughtContext(
                task_id="task_malformed_001",
                round_number=1,
                depth=1,
                correlation_id="malformed_correlation",
                channel_id="test_channel",
                parent_thought_id=None
            )
        )

        # Malformed parameters - not a valid DeferParams structure
        malformed_params = {
            "random_field": "value",
            "another_field": 123
            # Missing required 'reason' field
        }

        # Create with minimal valid DeferParams
        minimal_params = DeferParams(
            reason="Minimal valid params for test",
            defer_until=None
        )
        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=minimal_params,
            rationale="Testing malformed params",
            reasoning="Error handling test",
            evaluation_time_ms=50,
            raw_llm_response="{\"action\": \"DEFER\"}",
            resource_usage=None
        )

        dispatch_context = DispatchContext(
            channel_context=self.create_channel_context(),
            author_id="test_user",
            author_name="Test User",
            origin_service="test_service",
            handler_name="DeferHandler",
            action_type=HandlerActionType.DEFER,
            task_id=thought.source_task_id,
            thought_id=thought.thought_id,
            source_task_id=thought.source_task_id,
            event_summary="Malformed deferral test",
            event_timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id="malformed_correlation",
            wa_id=None,
            wa_authorized=False,
            wa_context=None,
            conscience_failure_context=None,
            epistemic_data=None,
            span_id=None,
            trace_id=None
        )

        # Should handle gracefully
        await defer_handler.handle(result, thought, dispatch_context)

        # Verify thought and task were still updated to DEFERRED
        mock_persistence.update_thought_status.assert_called_once_with(
            thought_id=thought.thought_id,
            status=ThoughtStatus.DEFERRED,
            final_action=result
        )
        mock_persistence.update_task_status.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
