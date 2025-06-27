"""
Integration tests for the complete deferral system.

Tests the full flow from handler -> bus -> WA service -> resolution,
including Discord adapter integration for human-in-the-loop scenarios.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import asyncio
from typing import List, Optional, Dict, Any

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
    
    def advance(self, seconds: int):
        """Advance time by given seconds."""
        self._now += timedelta(seconds=seconds)


class MockMemoryService:
    """Mock memory service for WA storage."""
    def __init__(self):
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
    def mock_time_service(self):
        """Provide a mock time service."""
        return MockTimeService()
    
    @pytest.fixture
    def mock_memory_service(self):
        """Provide a mock memory service."""
        return MockMemoryService()
    
    @pytest.fixture
    def mock_persistence(self, monkeypatch):
        """Mock persistence module."""
        mock = Mock()
        mock.update_thought_status = Mock()
        mock.update_task_status = Mock()
        mock.get_task_by_id = Mock(return_value=Task(
            task_id="test_task",
            description="Test task for integration",
            status=TaskStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        ))
        monkeypatch.setattr('ciris_engine.logic.handlers.control.defer_handler.persistence', mock)
        monkeypatch.setattr('ciris_engine.logic.services.governance.wise_authority.persistence', mock)
        return mock
    
    @pytest.fixture
    def mock_service_registry(self, mock_memory_service):
        """Create a mock service registry."""
        registry = Mock()
        
        # Mock WA service
        wa_service = WiseAuthorityService(
            memory_service=mock_memory_service,
            time_service=MockTimeService()
        )
        
        def get_service(handler=None, service_type=None):
            if service_type == ServiceType.WISE_AUTHORITY or service_type == "wise_authority":
                return wa_service
            elif handler == "task_scheduler" and service_type == "scheduler":
                scheduler = AsyncMock()
                scheduler.schedule_deferred_task = AsyncMock(
                    return_value=Mock(task_id="scheduled_123")
                )
                return scheduler
            return None
        
        registry.get_service = Mock(side_effect=get_service)
        return registry
    
    @pytest.fixture
    def bus_manager(self, mock_service_registry, mock_time_service):
        """Create a real bus manager with WiseBus."""
        manager = BusManager(mock_service_registry, time_service=mock_time_service)
        
        # Create real WiseBus
        manager.wise = WiseBus(mock_service_registry, mock_time_service)
        
        # Mock audit bus
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        manager.audit = mock_audit
        
        return manager
    
    @pytest.fixture
    def defer_handler(self, bus_manager, mock_time_service, mock_service_registry):
        """Create a defer handler with real dependencies."""
        deps = ActionHandlerDependencies(
            bus_manager=bus_manager,
            time_service=mock_time_service
        )
        handler = DeferHandler(deps)
        handler._service_registry = mock_service_registry
        return handler
    
    def create_channel_context(self, channel_id: str = "test_channel"):
        """Helper to create channel context."""
        from ciris_engine.schemas.runtime.system_context import ChannelContext
        return ChannelContext(
            channel_id=channel_id,
            channel_name=f"Channel {channel_id}",
            channel_type="text",
            created_at=datetime.now(timezone.utc)
        )


class TestDeferralIntegration(IntegrationTestBase):
    """Test complete deferral flow integration."""
    
    @pytest.mark.asyncio
    async def test_full_deferral_flow(
        self,
        defer_handler,
        mock_persistence,
        mock_memory_service,
        mock_service_registry
    ):
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
            context=ThoughtContext(
                task_id="task_medical_001",
                round_number=1,
                depth=1,
                correlation_id="medical_correlation"
            )
        )
        
        params = DeferParams(
            reason="Medical decision requires licensed physician review",
            context={
                "patient_id": "p12345",
                "symptoms": "chest_pain",
                "risk_level": "high"
            }
        )
        
        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=params.model_dump(),
            rationale="Medical decisions require human doctor",
            confidence=0.99,
            reasoning="High risk medical case",
            evaluation_time_ms=50
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
            correlation_id="medical_correlation"
        )
        
        # Execute deferral
        await defer_handler.handle(result, thought, dispatch_context)
        
        # Verify deferral was stored (through WA service)
        wa_service = mock_service_registry.get_service(service_type=ServiceType.WISE_AUTHORITY)
        
        # Step 2: List pending deferrals
        pending = await wa_service.get_pending_deferrals()
        assert len(pending) > 0
        
        medical_deferral = next(
            (d for d in pending if d.thought_id == "thought_medical_001"),
            None
        )
        assert medical_deferral is not None
        assert medical_deferral.reason == params.reason
        assert medical_deferral.priority == "medium"  # Default from handler
        
        # Step 3: WA resolves deferral
        wa_cert = WACertificate(
            wa_id="wa_doctor_001",
            name="Dr. Smith",
            role=WARole.AUTHORITY,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            public_key="test_public_key",
            signature="test_signature",
            scopes=["medical_decisions", "resolve_deferrals"],
            is_active=True
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
        defer_handler,
        mock_persistence,
        mock_service_registry
    ):
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
                thought_id=deferral_data["thought_id"],
                source_task_id=deferral_data["task_id"],
                content=f"Content for {deferral_data['thought_id']}",
                status=ThoughtStatus.PROCESSING,
                thought_depth=1,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                context=ThoughtContext(
                    task_id=deferral_data["task_id"],
                    round_number=1,
                    depth=1,
                    correlation_id=f"corr_{deferral_data['thought_id']}"
                )
            )
            
            params = DeferParams(
                reason=deferral_data["reason"],
                context=deferral_data["context"]
            )
            
            result = ActionSelectionDMAResult(
                selected_action=HandlerActionType.DEFER,
                action_parameters=params.model_dump(),
                rationale=f"Deferring {deferral_data['thought_id']}",
                confidence=0.9,
                reasoning="Priority-based deferral",
                evaluation_time_ms=100
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
                correlation_id=f"corr_{thought.thought_id}"
            )
            
            task = defer_handler.handle(result, thought, dispatch_context)
            tasks.append(task)
        
        # Execute all deferrals concurrently
        await asyncio.gather(*tasks)
        
        # Get WA service and check deferrals
        wa_service = mock_service_registry.get_service(service_type=ServiceType.WISE_AUTHORITY)
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
        
        # All should have default "medium" priority from handler
        # (The context priority is stored but not used for WA priority)
        assert critical.priority == "medium"
        assert high.priority == "medium"
        assert low.priority == "medium"
    
    @pytest.mark.asyncio
    async def test_time_based_deferral_with_scheduler(
        self,
        defer_handler,
        mock_persistence,
        mock_service_registry,
        mock_time_service
    ):
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
            context=ThoughtContext(
                task_id="task_scheduled_001",
                round_number=1,
                depth=1,
                correlation_id="payment_correlation"
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
            action_parameters=params.model_dump(),
            rationale="Payment processing requires time",
            confidence=0.95,
            reasoning="External system dependency",
            evaluation_time_ms=75
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
            correlation_id="payment_correlation"
        )
        
        # Execute deferral
        await defer_handler.handle(result, thought, dispatch_context)
        
        # Verify scheduler was called
        scheduler = mock_service_registry.get_service(
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
        wa_service = mock_service_registry.get_service(service_type=ServiceType.WISE_AUTHORITY)
        pending = await wa_service.get_pending_deferrals()
        
        scheduled_deferral = next(
            (d for d in pending if d.thought_id == "thought_scheduled_001"),
            None
        )
        assert scheduled_deferral is not None
    
    @pytest.mark.asyncio
    async def test_deferral_modification_by_wa(
        self,
        defer_handler,
        mock_persistence,
        mock_service_registry,
        mock_time_service
    ):
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
            context=ThoughtContext(
                task_id="task_modify_001",
                round_number=1,
                depth=1,
                correlation_id="finance_correlation"
            )
        )
        
        params = DeferParams(
            reason="Large transaction requires approval",
            context={
                "amount": "100000",
                "currency": "USD",
                "recipient": "offshore_account"
            }
        )
        
        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=params.model_dump(),
            rationale="High value transaction needs review",
            confidence=0.98,
            reasoning="Risk management protocol",
            evaluation_time_ms=90
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
            correlation_id="finance_correlation"
        )
        
        # Handle deferral
        await defer_handler.handle(result, thought, dispatch_context)
        
        # Get the deferral
        wa_service = mock_service_registry.get_service(service_type=ServiceType.WISE_AUTHORITY)
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
        defer_handler,
        mock_persistence,
        mock_service_registry
    ):
        """Test graceful handling when WA service is unavailable."""
        # Make WA service unavailable
        original_get_service = mock_service_registry.get_service
        
        def failing_get_service(handler=None, service_type=None):
            if service_type == ServiceType.WISE_AUTHORITY or service_type == "wise_authority":
                return None  # Service unavailable
            return original_get_service(handler, service_type)
        
        mock_service_registry.get_service = Mock(side_effect=failing_get_service)
        
        # Create deferral
        thought = Thought(
            thought_id="thought_no_wa_001",
            source_task_id="task_no_wa_001",
            content="Decision without WA service",
            status=ThoughtStatus.PROCESSING,
            thought_depth=1,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            context=ThoughtContext(
                task_id="task_no_wa_001",
                round_number=1,
                depth=1,
                correlation_id="no_wa_correlation"
            )
        )
        
        params = DeferParams(
            reason="Test deferral without WA service",
            context={"test": "no_wa_scenario"}
        )
        
        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=params.model_dump(),
            rationale="Testing WA unavailability",
            confidence=0.8,
            reasoning="Resilience test",
            evaluation_time_ms=100
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
            correlation_id="no_wa_correlation"
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
        defer_handler,
        mock_persistence,
        bus_manager
    ):
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
            context=ThoughtContext(
                task_id="task_malformed_001",
                round_number=1,
                depth=1,
                correlation_id="malformed_correlation"
            )
        )
        
        # Malformed parameters - not a valid DeferParams structure
        malformed_params = {
            "random_field": "value",
            "another_field": 123
            # Missing required 'reason' field
        }
        
        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.DEFER,
            action_parameters=malformed_params,
            rationale="Testing malformed params",
            confidence=0.7,
            reasoning="Error handling test",
            evaluation_time_ms=50
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
            correlation_id="malformed_correlation"
        )
        
        # Should handle gracefully
        await defer_handler.handle(result, thought, dispatch_context)
        
        # Should still send error deferral
        wise_bus_calls = bus_manager.wise.send_deferral.call_args_list
        assert len(wise_bus_calls) > 0
        
        # Check error context was sent
        error_context = wise_bus_calls[0].kwargs['context']
        assert error_context.reason == "parameter_error"
        assert error_context.metadata["error_type"] == "parameter_parsing_error"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])