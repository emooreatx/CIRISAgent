"""
Unit tests for SelfConfigurationService.

Tests the master orchestrator that coordinates identity variance monitoring,
pattern detection, and configuration adaptation within safe ethical bounds.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from typing import List, Dict, Any

from ciris_engine.services.self_configuration_service import (
    SelfConfigurationService,
    AdaptationState,
    AdaptationCycle
)
from ciris_engine.services.identity_variance_monitor import VarianceReport
from ciris_engine.schemas.graph_schemas_v1 import (
    GraphNode, GraphScope, NodeType, AdaptationProposalNode
)
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot


class TestSelfConfigurationService:
    """Test suite for SelfConfigurationService."""
    
    @pytest.fixture
    def mock_memory_bus(self):
        """Create a mock memory bus."""
        bus = AsyncMock()
        bus.memorize = AsyncMock()
        bus.recall = AsyncMock(return_value=[])
        return bus
    
    @pytest.fixture
    def mock_variance_monitor(self):
        """Create a mock variance monitor."""
        monitor = AsyncMock()
        monitor.initialize_baseline = AsyncMock(return_value="baseline_123")
        monitor.check_variance = AsyncMock()
        monitor.start = AsyncMock()
        monitor.stop = AsyncMock()
        monitor.is_healthy = AsyncMock(return_value=True)
        return monitor
    
    @pytest.fixture
    def mock_feedback_loop(self):
        """Create a mock feedback loop."""
        loop = AsyncMock()
        loop.analyze_and_adapt = AsyncMock(return_value={
            "patterns_detected": 5,
            "proposals_generated": 3,
            "adaptations_applied": 2
        })
        loop._apply_configuration_changes = AsyncMock(return_value=True)
        loop.start = AsyncMock()
        loop.stop = AsyncMock()
        loop.is_healthy = AsyncMock(return_value=True)
        return loop
    
    @pytest.fixture
    def mock_telemetry_service(self):
        """Create a mock telemetry service."""
        service = AsyncMock()
        service.process_system_snapshot = AsyncMock(return_value={
            "snapshot_processed": True,
            "memories_created": 5
        })
        service.start = AsyncMock()
        service.stop = AsyncMock()
        service.is_healthy = AsyncMock(return_value=True)
        return service
    
    @pytest.fixture
    def self_config_service(self, mock_memory_bus):
        """Create a SelfConfigurationService instance."""
        service = SelfConfigurationService(
            memory_bus=mock_memory_bus,
            variance_threshold=0.20,
            adaptation_interval_hours=6,
            stabilization_period_hours=24
        )
        return service
    
    @pytest.fixture
    def sample_identity(self):
        """Create a sample agent identity."""
        identity = MagicMock(spec=AgentIdentityRoot)
        identity.agent_id = "test_agent"
        return identity
    
    @pytest.fixture
    def sample_snapshot(self):
        """Create a sample system snapshot."""
        return SystemSnapshot(
            agent_name="test_agent",
            network_status="active",
            isolation_hours=0,
            telemetry={"test": "data"}
        )
    
    def _inject_mocks(self, service, variance_monitor, feedback_loop, telemetry_service):
        """Inject mock components into service."""
        service._variance_monitor = variance_monitor
        service._feedback_loop = feedback_loop
        service._telemetry_service = telemetry_service
    
    @pytest.mark.asyncio
    async def test_initialize_identity_baseline(
        self, self_config_service, mock_variance_monitor, sample_identity
    ):
        """Test identity baseline initialization."""
        self_config_service._variance_monitor = mock_variance_monitor
        
        baseline_id = await self_config_service.initialize_identity_baseline(sample_identity)
        
        assert baseline_id == "baseline_123"
        mock_variance_monitor.initialize_baseline.assert_called_once_with(sample_identity)
    
    @pytest.mark.asyncio
    async def test_process_experience(
        self, self_config_service, mock_telemetry_service, 
        sample_snapshot, mock_variance_monitor, mock_feedback_loop
    ):
        """Test processing an experience snapshot."""
        self._inject_mocks(
            self_config_service, mock_variance_monitor, 
            mock_feedback_loop, mock_telemetry_service
        )
        
        # Process experience
        result = await self_config_service.process_experience(
            sample_snapshot, "thought_123", "task_456"
        )
        
        assert result['snapshot_processed'] is True
        assert result['memories_created'] == 5
        
        # Verify telemetry was processed
        mock_telemetry_service.process_system_snapshot.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_adaptation_cycle_safe_variance(
        self, self_config_service, mock_variance_monitor, 
        mock_feedback_loop, mock_telemetry_service
    ):
        """Test adaptation cycle with variance within safe bounds."""
        self._inject_mocks(
            self_config_service, mock_variance_monitor, 
            mock_feedback_loop, mock_telemetry_service
        )
        
        # Mock safe variance
        variance_report = VarianceReport(
            timestamp=datetime.now(timezone.utc),
            baseline_snapshot_id="baseline_123",
            current_snapshot_id="current_456",
            total_variance=0.15,  # Below 20% threshold
            variance_by_impact={},
            differences=[],
            requires_wa_review=False,
            recommendations=[]
        )
        mock_variance_monitor.check_variance.return_value = variance_report
        
        # Mock proposals
        proposals = [
            AdaptationProposalNode(
                trigger="Test pattern",
                proposed_changes={"test": "change"},
                evidence=[],
                confidence=0.9,
                auto_applicable=True,
                scope=GraphScope.LOCAL
            )
        ]
        
        with patch.object(self_config_service, '_get_pending_proposals', return_value=proposals):
            with patch.object(self_config_service, '_filter_safe_proposals', return_value=proposals):
                with patch.object(self_config_service, '_apply_proposals', return_value=1):
                    result = await self_config_service._run_adaptation_cycle()
        
        assert result['status'] == 'completed'
        assert result['variance_before'] == 0.15
        assert result['changes_applied'] == 1
        assert self_config_service._current_state == AdaptationState.STABILIZING
    
    @pytest.mark.asyncio
    async def test_adaptation_cycle_high_variance(
        self, self_config_service, mock_variance_monitor,
        mock_feedback_loop, mock_telemetry_service
    ):
        """Test adaptation cycle with variance exceeding threshold."""
        self._inject_mocks(
            self_config_service, mock_variance_monitor, 
            mock_feedback_loop, mock_telemetry_service
        )
        
        # Mock high variance
        variance_report = VarianceReport(
            timestamp=datetime.now(timezone.utc),
            baseline_snapshot_id="baseline_123",
            current_snapshot_id="current_456",
            total_variance=0.25,  # Above 20% threshold
            variance_by_impact={},
            differences=[],
            requires_wa_review=True,
            recommendations=["Variance too high"]
        )
        mock_variance_monitor.check_variance.return_value = variance_report
        
        result = await self_config_service._run_adaptation_cycle()
        
        assert result['status'] == 'wa_review_required'
        assert result['variance'] == 0.25
        assert self_config_service._current_state == AdaptationState.REVIEWING
    
    @pytest.mark.asyncio
    async def test_safe_proposal_filtering(self, self_config_service):
        """Test filtering proposals to stay within variance bounds."""
        current_variance = 0.15
        
        proposals = [
            AdaptationProposalNode(
                trigger="Local change",
                proposed_changes={"tool_prefs": "change"},
                evidence=[],
                confidence=0.9,
                scope=GraphScope.LOCAL  # 2% impact
            ),
            AdaptationProposalNode(
                trigger="Identity change",
                proposed_changes={"behavior": "change"},
                evidence=[],
                confidence=0.9,
                scope=GraphScope.IDENTITY  # 10% impact
            )
        ]
        
        # With 15% current variance, only LOCAL change should be safe
        safe = await self_config_service._filter_safe_proposals(proposals, current_variance)
        
        assert len(safe) == 1
        assert safe[0].scope == GraphScope.LOCAL
    
    @pytest.mark.asyncio
    async def test_emergency_stop(self, self_config_service, mock_memory_bus):
        """Test emergency stop activation."""
        await self_config_service.emergency_stop("Critical error detected")
        
        assert self_config_service._emergency_stop is True
        
        # Verify emergency stop was recorded
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args
        # Get the first positional argument (node)
        stop_node = call_args[0][0]
        assert stop_node.attributes['event_type'] == 'emergency_stop'
        assert stop_node.attributes['reason'] == 'Critical error detected'
    
    @pytest.mark.asyncio
    async def test_consecutive_failure_handling(
        self, self_config_service, mock_variance_monitor
    ):
        """Test that consecutive failures trigger emergency stop."""
        self_config_service._variance_monitor = mock_variance_monitor
        
        # Simulate failures
        mock_variance_monitor.check_variance.side_effect = Exception("Test error")
        
        # Run cycles until emergency stop
        for i in range(3):
            result = await self_config_service._run_adaptation_cycle()
            assert result['status'] == 'failed'
        
        assert self_config_service._consecutive_failures == 3
        assert self_config_service._emergency_stop is True
    
    @pytest.mark.asyncio
    async def test_resume_after_review(self, self_config_service, mock_memory_bus):
        """Test resuming after WA review."""
        self_config_service._current_state = AdaptationState.REVIEWING
        
        review_outcome = {
            "approved": True,
            "feedback": "Changes approved"
        }
        
        await self_config_service.resume_after_review(review_outcome)
        
        assert self_config_service._current_state == AdaptationState.STABILIZING
        assert self_config_service._consecutive_failures == 0
        
        # Verify outcome was recorded
        mock_memory_bus.memorize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_adaptation_status(self, self_config_service):
        """Test getting adaptation status."""
        # Create some history
        self_config_service._adaptation_history = [
            AdaptationCycle(
                cycle_id="cycle_1",
                started_at=datetime.now(timezone.utc) - timedelta(hours=2),
                state=AdaptationState.LEARNING,
                patterns_detected=5,
                proposals_generated=3,
                changes_applied=2,
                variance_before=0.1,
                variance_after=0.12,
                completed_at=datetime.now(timezone.utc) - timedelta(hours=1)
            )
        ]
        
        status = await self_config_service.get_adaptation_status()
        
        assert status['current_state'] == AdaptationState.LEARNING.value
        assert status['cycles_completed'] == 1
        assert len(status['recent_history']) == 1
        assert status['recent_history'][0]['changes_applied'] == 2
    
    @pytest.mark.asyncio
    async def test_should_run_adaptation_check(self, self_config_service):
        """Test conditions for running adaptation cycle."""
        # Emergency stop prevents running
        self_config_service._emergency_stop = True
        assert await self_config_service._should_run_adaptation_cycle() is False
        
        self_config_service._emergency_stop = False
        
        # Active cycle prevents running
        self_config_service._current_cycle = AdaptationCycle(
            cycle_id="active",
            started_at=datetime.now(timezone.utc),
            state=AdaptationState.ADAPTING,
            patterns_detected=0,
            proposals_generated=0,
            changes_applied=0,
            variance_before=0.0,
            variance_after=None,
            completed_at=None
        )
        assert await self_config_service._should_run_adaptation_cycle() is False
        
        # Completed cycle allows running
        self_config_service._current_cycle.completed_at = datetime.now(timezone.utc)
        self_config_service._last_adaptation = datetime.now(timezone.utc) - timedelta(hours=7)
        assert await self_config_service._should_run_adaptation_cycle() is True
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(
        self, self_config_service, mock_variance_monitor,
        mock_feedback_loop, mock_telemetry_service
    ):
        """Test service start/stop lifecycle."""
        self._inject_mocks(
            self_config_service, mock_variance_monitor,
            mock_feedback_loop, mock_telemetry_service
        )
        
        # Start services
        await self_config_service.start()
        
        mock_variance_monitor.start.assert_called_once()
        mock_feedback_loop.start.assert_called_once()
        mock_telemetry_service.start.assert_called_once()
        
        # Stop services
        await self_config_service.stop()
        
        mock_variance_monitor.stop.assert_called_once()
        mock_feedback_loop.stop.assert_called_once()
        mock_telemetry_service.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check(
        self, self_config_service, mock_variance_monitor,
        mock_feedback_loop, mock_telemetry_service
    ):
        """Test health check."""
        self._inject_mocks(
            self_config_service, mock_variance_monitor,
            mock_feedback_loop, mock_telemetry_service
        )
        
        # All healthy
        assert await self_config_service.is_healthy() is True
        
        # Emergency stop makes unhealthy
        self_config_service._emergency_stop = True
        assert await self_config_service.is_healthy() is False
        
        # Component failure makes unhealthy
        self_config_service._emergency_stop = False
        mock_variance_monitor.is_healthy.return_value = False
        assert await self_config_service.is_healthy() is False
    
    def test_capabilities(self, self_config_service):
        """Test service capabilities list."""
        capabilities = asyncio.run(self_config_service.get_capabilities())
        expected = [
            "autonomous_adaptation", "identity_variance_monitoring", "pattern_detection",
            "configuration_feedback", "safe_adaptation", "wa_review_integration",
            "emergency_stop", "adaptation_history", "experience_processing"
        ]
        assert set(capabilities) == set(expected)