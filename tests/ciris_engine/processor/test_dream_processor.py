"""
Unit tests for DreamProcessor.

Tests the dream processor that integrates memory consolidation, self-configuration,
and introspection during dream cycles.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock
from typing import List, Dict, Any
import asyncio

from ciris_engine.processor.dream_processor import (
    DreamProcessor,
    DreamPhase,
    DreamSession
)
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.memory_schemas_v1 import MemoryQuery
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


class TestDreamProcessor:
    """Test suite for DreamProcessor."""
    
    @pytest.fixture
    def mock_app_config(self):
        """Create mock app configuration."""
        config = MagicMock(spec=AppConfig)
        config.cirisnode = MagicMock()
        config.cirisnode.base_url = None  # CIRISNode disabled by default
        return config
    
    @pytest.fixture
    def mock_service_registry(self):
        """Create mock service registry."""
        registry = AsyncMock()
        return registry
    
    @pytest.fixture
    def mock_identity_manager(self):
        """Create mock identity manager."""
        manager = MagicMock()
        manager.agent_identity = MagicMock()
        manager.agent_identity.agent_id = "test_agent"
        return manager
    
    @pytest.fixture
    def mock_memory_bus(self):
        """Create mock memory bus."""
        bus = AsyncMock()
        bus.memorize = AsyncMock()
        bus.recall = AsyncMock(return_value=[])
        return bus
    
    @pytest.fixture
    def mock_communication_bus(self):
        """Create mock communication bus."""
        bus = AsyncMock()
        bus.send_message = AsyncMock()
        return bus
    
    @pytest.fixture
    def mock_self_config_service(self):
        """Create mock self-configuration service."""
        service = AsyncMock()
        service.initialize_identity_baseline = AsyncMock()
        service.process_experience = AsyncMock(return_value={
            "adaptation_triggered": True,
            "adaptation_result": {"changes_applied": 2}
        })
        return service
    
    @pytest.fixture
    def mock_telemetry_service(self):
        """Create mock telemetry service."""
        service = AsyncMock()
        service.consolidate_memories_with_grace = AsyncMock(return_value={
            "memories_consolidated": 42,
            "wisdom_note": "Grace creates understanding"
        })
        return service
    
    @pytest.fixture
    def dream_processor(self, mock_app_config, mock_service_registry, mock_identity_manager):
        """Create DreamProcessor instance."""
        processor = DreamProcessor(
            app_config=mock_app_config,
            service_registry=mock_service_registry,
            identity_manager=mock_identity_manager,
            startup_channel_id="test_channel",
            min_dream_duration=30,
            max_dream_duration=120
        )
        return processor
    
    def _inject_services(self, processor, self_config, telemetry, memory_bus, comm_bus):
        """Inject mock services into processor."""
        processor.self_config_service = self_config
        processor.telemetry_service = telemetry
        processor.memory_bus = memory_bus
        processor.communication_bus = comm_bus
    
    @pytest.mark.asyncio
    async def test_cirisnode_detection(self, mock_app_config):
        """Test CIRISNode configuration detection."""
        # Disabled by default
        processor = DreamProcessor(mock_app_config, None)
        assert processor.cirisnode_enabled is False
        
        # Enabled with valid URL
        mock_app_config.cirisnode.base_url = "https://cirisnode.example.com"
        processor = DreamProcessor(mock_app_config, None)
        assert processor.cirisnode_enabled is True
    
    @pytest.mark.asyncio
    async def test_dream_entry_announcement(
        self, dream_processor, mock_communication_bus
    ):
        """Test dream entry announcement to channel."""
        dream_processor.communication_bus = mock_communication_bus
        
        await dream_processor._announce_dream_entry(1800)  # 30 minutes
        
        mock_communication_bus.send_message.assert_called_once()
        call_args = mock_communication_bus.send_message.call_args
        assert "self-reflection mode" in call_args[1]['content']
        assert "30 minutes" in call_args[1]['content']
        assert call_args[1]['channel_id'] == "test_channel"
    
    @pytest.mark.asyncio
    async def test_dream_session_creation(self, dream_processor):
        """Test dream session initialization."""
        # Mock the event loop
        with patch.object(dream_processor, '_dream_loop', new_callable=AsyncMock):
            await dream_processor.start_dreaming(duration=1800)
        
        assert dream_processor.current_session is not None
        assert dream_processor.current_session.phase == DreamPhase.ENTERING
        assert dream_processor.current_session.planned_duration == timedelta(seconds=1800)
        assert dream_processor.dream_metrics['total_dreams'] == 1
    
    @pytest.mark.asyncio
    async def test_memory_consolidation_phase(
        self, dream_processor, mock_telemetry_service
    ):
        """Test memory consolidation during dreams."""
        dream_processor.telemetry_service = mock_telemetry_service
        dream_processor.current_session = DreamSession(
            session_id="test_dream",
            scheduled_start=None,
            actual_start=datetime.now(timezone.utc),
            planned_duration=timedelta(minutes=30),
            phase=DreamPhase.CONSOLIDATING
        )
        
        await dream_processor._consolidation_phase()
        
        mock_telemetry_service.consolidate_memories_with_grace.assert_called_once()
        assert dream_processor.current_session.memories_consolidated == 42
        assert "Grace creates understanding" in dream_processor.current_session.insights_gained
    
    @pytest.mark.asyncio
    async def test_ponder_question_analysis(self, dream_processor, mock_memory_bus):
        """Test analysis of PONDER questions during dreams."""
        # Mock PONDER thoughts
        ponder_thoughts = [
            GraphNode(
                id="thought_1",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={
                    "action": HandlerActionType.PONDER.value,
                    "ponder_data": {
                        "questions": ["Why do I make mistakes?", "How can I improve?"]
                    }
                }
            ),
            GraphNode(
                id="thought_2",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={
                    "action": HandlerActionType.PONDER.value,
                    "ponder_data": {
                        "questions": ["What is my purpose?"]
                    }
                }
            )
        ]
        
        dream_processor.memory_bus = mock_memory_bus
        mock_memory_bus.recall.return_value = ponder_thoughts
        
        questions = await dream_processor._recall_recent_ponder_questions()
        
        assert len(questions) == 3
        assert "Why do I make mistakes?" in questions
        assert "What is my purpose?" in questions
    
    @pytest.mark.asyncio
    async def test_ponder_pattern_insights(self, dream_processor):
        """Test insight generation from PONDER patterns."""
        questions = [
            "Why did that fail?",
            "How can I understand better?",
            "What should I improve?",
            "Why is this confusing?",
            "How do I serve users better?"
        ]
        
        insights = dream_processor._analyze_ponder_patterns(questions)
        
        assert len(insights) > 0
        # Should identify themes
        assert any("introspection focused on" in i for i in insights)
    
    @pytest.mark.asyncio
    async def test_self_configuration_phase(
        self, dream_processor, mock_self_config_service
    ):
        """Test self-configuration during dreams."""
        dream_processor.self_config_service = mock_self_config_service
        dream_processor.current_session = DreamSession(
            session_id="test_dream",
            scheduled_start=None,
            actual_start=datetime.now(timezone.utc),
            planned_duration=timedelta(minutes=30),
            phase=DreamPhase.CONFIGURING
        )
        
        await dream_processor._configuration_phase()
        
        mock_self_config_service.process_experience.assert_called_once()
        assert dream_processor.current_session.adaptations_made == 2
    
    @pytest.mark.asyncio
    async def test_future_dream_scheduling(self, dream_processor, mock_memory_bus):
        """Test scheduling of next dream session."""
        dream_processor.memory_bus = mock_memory_bus
        
        task_id = await dream_processor._schedule_next_dream()
        
        assert task_id is not None
        mock_memory_bus.memorize.assert_called_once()
        
        call_args = mock_memory_bus.memorize.call_args
        dream_task = call_args[1]['node']
        
        assert dream_task.attributes['task_type'] == 'scheduled_dream'
        assert dream_task.attributes['duration_minutes'] == 30
        assert dream_task.attributes['can_defer'] is True
    
    @pytest.mark.asyncio
    async def test_future_work_planning(self, dream_processor, mock_memory_bus):
        """Test planning future work based on insights."""
        dream_processor.memory_bus = mock_memory_bus
        dream_processor.current_session = DreamSession(
            session_id="test_dream",
            scheduled_start=None,
            actual_start=datetime.now(timezone.utc),
            planned_duration=timedelta(minutes=30),
            phase=DreamPhase.PLANNING
        )
        
        # Add insights that trigger planning
        dream_processor.current_session.insights_gained = [
            "Recent introspection focused on: identity",
            "recurring contemplations indicate areas needing resolution"
        ]
        
        future_tasks = await dream_processor._plan_future_work()
        
        assert len(future_tasks) == 2
        # Should have created tasks for both insights
        assert mock_memory_bus.memorize.call_count == 2
    
    @pytest.mark.asyncio
    async def test_dream_exit_announcement(
        self, dream_processor, mock_communication_bus
    ):
        """Test dream exit announcement."""
        dream_processor.communication_bus = mock_communication_bus
        dream_processor.current_session = DreamSession(
            session_id="test_dream",
            scheduled_start=None,
            actual_start=datetime.now(timezone.utc),
            planned_duration=timedelta(minutes=30),
            phase=DreamPhase.EXITING,
            memories_consolidated=42,
            adaptations_made=3,
            insights_gained=["Test insight 1", "Test insight 2"]
        )
        
        await dream_processor._announce_dream_exit()
        
        mock_communication_bus.send_message.assert_called_once()
        call_args = mock_communication_bus.send_message.call_args
        content = call_args[1]['content']
        
        assert "Self-reflection complete" in content
        assert "2 insights gained" in content
        assert "42 memories" in content
        assert "3 adaptations" in content
    
    @pytest.mark.asyncio
    async def test_dream_journal_recording(self, dream_processor, mock_memory_bus):
        """Test dream session recording in memory."""
        dream_processor.memory_bus = mock_memory_bus
        dream_processor.current_session = DreamSession(
            session_id="test_dream",
            scheduled_start=None,
            actual_start=datetime.now(timezone.utc) - timedelta(minutes=30),
            planned_duration=timedelta(minutes=30),
            phase=DreamPhase.EXITING,
            memories_consolidated=42,
            patterns_analyzed=5,
            adaptations_made=2,
            completed_at=datetime.now(timezone.utc)
        )
        
        await dream_processor._record_dream_session()
        
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args
        journal_entry = call_args[1]['node']
        
        assert journal_entry.type == NodeType.CONCEPT
        assert journal_entry.scope == GraphScope.IDENTITY
        assert journal_entry.attributes['memories_consolidated'] == 42
        assert journal_entry.attributes['patterns_analyzed'] == 5
    
    @pytest.mark.asyncio
    async def test_dream_health_check(self, dream_processor):
        """Test checking if dream is needed based on timing."""
        # No previous dreams - should recommend
        assert dream_processor.should_enter_dream_state(400) is True
        
        # Recent dream - should not recommend
        dream_processor.dream_metrics['end_time'] = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).isoformat()
        assert dream_processor.should_enter_dream_state(400) is False
        
        # Old dream - should recommend
        dream_processor.dream_metrics['end_time'] = (
            datetime.now(timezone.utc) - timedelta(hours=7)
        ).isoformat()
        assert dream_processor.should_enter_dream_state(400) is True
    
    @pytest.mark.asyncio
    async def test_dream_summary(self, dream_processor):
        """Test getting dream summary."""
        # No active dream
        summary = dream_processor.get_dream_summary()
        assert summary['state'] == 'awake'
        assert summary['current_session'] is None
        
        # With active session
        dream_processor.current_session = DreamSession(
            session_id="test_dream",
            scheduled_start=None,
            actual_start=datetime.now(timezone.utc) - timedelta(minutes=15),
            planned_duration=timedelta(minutes=30),
            phase=DreamPhase.ANALYZING,
            memories_consolidated=20,
            insights_gained=["insight1", "insight2"]
        )
        
        # Mock active task
        dream_processor._dream_task = MagicMock()
        dream_processor._dream_task.done.return_value = False
        
        summary = dream_processor.get_dream_summary()
        assert summary['state'] == 'dreaming'
        assert summary['current_session']['phase'] == 'analyzing'
        assert summary['current_session']['insights_count'] == 2
    
    @pytest.mark.asyncio
    async def test_dream_interruption(self, dream_processor):
        """Test graceful dream interruption."""
        # Create a real asyncio task that we can control
        async def mock_dream_loop():
            await asyncio.sleep(100)  # Long sleep to simulate ongoing work
            
        dream_processor._dream_task = asyncio.create_task(mock_dream_loop())
        
        # Create real asyncio event
        dream_processor._stop_event = asyncio.Event()
        
        # Run stop_dreaming
        await dream_processor.stop_dreaming()
        
        # Should have set stop event
        assert dream_processor._stop_event.is_set()
        
        # Task should be done (cancelled)
        assert dream_processor._dream_task.done()
    
    @pytest.mark.asyncio
    async def test_service_initialization(
        self, dream_processor, mock_service_registry
    ):
        """Test initialization of required services."""
        dream_processor.service_registry = mock_service_registry
        
        with patch('ciris_engine.processor.dream_processor.MemoryBus') as MockMemoryBus:
            with patch('ciris_engine.processor.dream_processor.CommunicationBus') as MockCommBus:
                with patch('ciris_engine.processor.dream_processor.SelfConfigurationService') as MockSelfConfig:
                    with patch('ciris_engine.processor.dream_processor.UnifiedTelemetryService') as MockTelemetry:
                        await dream_processor._initialize_services()
        
        assert dream_processor.memory_bus is not None
        assert dream_processor.communication_bus is not None
        assert dream_processor.self_config_service is not None
        assert dream_processor.telemetry_service is not None
    
    @pytest.mark.asyncio
    async def test_phase_duration_tracking(self, dream_processor):
        """Test tracking of phase durations."""
        dream_processor.current_session = DreamSession(
            session_id="test_dream",
            scheduled_start=None,
            actual_start=datetime.now(timezone.utc),
            planned_duration=timedelta(minutes=30),
            phase=DreamPhase.CONSOLIDATING
        )
        
        start_time = datetime.now(timezone.utc)
        await asyncio.sleep(0.1)  # Brief delay
        dream_processor._record_phase_duration(DreamPhase.CONSOLIDATING, start_time)
        
        assert DreamPhase.CONSOLIDATING.value in dream_processor.current_session.phase_durations
        duration = dream_processor.current_session.phase_durations[DreamPhase.CONSOLIDATING.value]
        assert duration > 0
    
    @pytest.mark.asyncio
    async def test_benchmarking_disabled_without_cirisnode(self, dream_processor):
        """Test that benchmarking is skipped when CIRISNode is not configured."""
        dream_processor.cirisnode_enabled = False
        
        # Should not create client
        assert dream_processor.cirisnode_client is None
        
        # Benchmarking phase should be skipped
        # This is tested implicitly in the full dream loop test