"""
Unit tests for ConfigurationFeedbackLoop service.

Tests the pattern detection and adaptation proposal system that enables
autonomous configuration updates based on observed patterns.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from ciris_engine.services.configuration_feedback_loop import (
    ConfigurationFeedbackLoop,
    PatternType,
    DetectedPattern,
    ConfigurationUpdate,
    AdaptationProposalNode
)
from ciris_engine.schemas.graph_schemas_v1 import (
    GraphNode, GraphScope, NodeType, ConfigNodeType, CONFIG_SCOPE_MAP
)
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryOpResult
from ciris_engine.schemas.protocol_schemas_v1 import TimeSeriesDataPoint


class TestConfigurationFeedbackLoop:
    """Test suite for ConfigurationFeedbackLoop."""
    
    @pytest.fixture
    def mock_memory_bus(self):
        """Create a mock memory bus."""
        bus = AsyncMock()
        bus.memorize = AsyncMock(return_value=MemoryOpResult(status=MemoryOpStatus.OK))
        bus.recall = AsyncMock(return_value=[])
        bus.recall_timeseries = AsyncMock(return_value=[])
        return bus
    
    @pytest.fixture
    def feedback_loop(self, mock_memory_bus):
        """Create a ConfigurationFeedbackLoop instance."""
        loop = ConfigurationFeedbackLoop(
            memory_bus=mock_memory_bus,
            pattern_threshold=0.7,
            adaptation_threshold=0.8,
            analysis_interval_hours=6
        )
        return loop
    
    @pytest.fixture
    def sample_metrics_data(self):
        """Create sample metrics data for testing."""
        base_time = datetime.now(timezone.utc)
        return [
            TimeSeriesDataPoint(
                timestamp=base_time - timedelta(hours=i),
                metric_name="response_time",
                value=100 + i * 10,  # Degrading over time
                correlation_type="METRIC_DATAPOINT",
                tags={"metric_type": "performance"},
                source=f"metric_{i}"
            )
            for i in range(20)
        ]
    
    @pytest.fixture
    def sample_action_data(self):
        """Create sample action data for testing."""
        base_time = datetime.now(timezone.utc)
        actions = []
        
        # Morning tool usage pattern
        for i in range(10):
            actions.append(TimeSeriesDataPoint(
                timestamp=base_time.replace(hour=9) - timedelta(days=i),
                metric_name="action_count",
                value=1.0,
                correlation_type="AUDIT_EVENT",
                tags={"hour": "9", "action": "TOOL", "tool_name": "research_tool"},
                source=f"action_morning_{i}"
            ))
        
        # Evening tool usage pattern
        for i in range(10):
            actions.append(TimeSeriesDataPoint(
                timestamp=base_time.replace(hour=20) - timedelta(days=i),
                metric_name="action_count",
                value=1.0,
                correlation_type="AUDIT_EVENT",
                tags={"hour": "20", "action": "TOOL", "tool_name": "summary_tool"},
                source=f"action_evening_{i}"
            ))
        
        return actions
    
    @pytest.mark.asyncio
    async def test_temporal_pattern_detection(self, feedback_loop, mock_memory_bus, sample_action_data):
        """Test detection of temporal patterns in tool usage."""
        # Mock the recall for actions by hour
        mock_memory_bus.recall_timeseries.return_value = sample_action_data
        
        patterns = await feedback_loop._detect_temporal_patterns()
        
        # Should detect tool usage pattern
        temporal_patterns = [p for p in patterns if p.pattern_type == PatternType.TEMPORAL]
        assert len(temporal_patterns) > 0
        
        # Check pattern details
        tool_pattern = next((p for p in temporal_patterns if "tool_usage_by_hour" in p.pattern_id), None)
        assert tool_pattern is not None
        assert tool_pattern.confidence >= 0.8
        assert "morning_tools" in tool_pattern.metrics
        assert "evening_tools" in tool_pattern.metrics
    
    @pytest.mark.asyncio
    async def test_performance_degradation_detection(self, feedback_loop, mock_memory_bus, sample_metrics_data):
        """Test detection of performance degradation patterns."""
        mock_memory_bus.recall_timeseries.return_value = sample_metrics_data
        
        patterns = await feedback_loop._detect_performance_patterns()
        
        # Should detect degradation
        perf_patterns = [p for p in patterns if p.pattern_type == PatternType.PERFORMANCE]
        assert len(perf_patterns) > 0
        
        degradation_pattern = next(
            (p for p in perf_patterns if "degradation" in p.pattern_id), None
        )
        assert degradation_pattern is not None
        assert degradation_pattern.confidence > 0.7
        assert "degradation" in degradation_pattern.metrics
    
    @pytest.mark.asyncio
    async def test_frequency_pattern_detection(self, feedback_loop, mock_memory_bus):
        """Test detection of action frequency patterns."""
        # Mock action frequency data
        base_time = datetime.now(timezone.utc)
        action_data = [
            TimeSeriesDataPoint(
                timestamp=base_time - timedelta(minutes=i),
                metric_name="action_count",
                value=1.0,
                correlation_type="AUDIT_EVENT",
                tags={"action": "SPEAK"},
                source=f"speak_{i}"
            ) for i in range(60)
        ] + [
            TimeSeriesDataPoint(
                timestamp=base_time - timedelta(minutes=i+60),
                metric_name="action_count",
                value=1.0,
                correlation_type="AUDIT_EVENT",
                tags={"action": "MEMORIZE"},
                source=f"mem_{i}"
            ) for i in range(20)
        ] + [
            TimeSeriesDataPoint(
                timestamp=base_time - timedelta(minutes=i+80),
                metric_name="action_count",
                value=1.0,
                correlation_type="AUDIT_EVENT",
                tags={"action": "TOOL"},
                source=f"tool_{i}"
            ) for i in range(5)
        ]
        
        mock_memory_bus.recall_timeseries.return_value = action_data
        
        patterns = await feedback_loop._detect_frequency_patterns()
        
        # Should detect dominant action
        freq_patterns = [p for p in patterns if p.pattern_type == PatternType.FREQUENCY]
        dominant_patterns = [p for p in freq_patterns if "dominant" in p.pattern_id]
        assert len(dominant_patterns) > 0
        
        # SPEAK should be dominant (60/85 = ~70%)
        speak_pattern = next((p for p in dominant_patterns if "SPEAK" in p.pattern_id), None)
        assert speak_pattern is not None
        assert speak_pattern.metrics['percentage'] > 0.5
    
    @pytest.mark.asyncio
    async def test_error_pattern_detection(self, feedback_loop, mock_memory_bus):
        """Test detection of recurring error patterns."""
        # Mock error logs
        base_time = datetime.now(timezone.utc)
        error_data = [
            TimeSeriesDataPoint(
                timestamp=base_time - timedelta(hours=i),
                metric_name="error_count",
                value=1.0,
                correlation_type="LOG_ENTRY",
                tags={"log_level": "ERROR", "error_type": "timeout_error", "content": "Timeout error in tool execution"},
                source=f"error_{i}"
            )
            for i in range(5)
        ]
        
        mock_memory_bus.recall_timeseries.return_value = error_data
        
        patterns = await feedback_loop._detect_error_patterns()
        
        # Should detect recurring timeout errors
        error_patterns = [p for p in patterns if p.pattern_type == PatternType.ERROR]
        assert len(error_patterns) > 0
        
        timeout_pattern = next((p for p in error_patterns if "timeout" in p.pattern_id), None)
        assert timeout_pattern is not None
        assert timeout_pattern.metrics['count'] >= 3
    
    @pytest.mark.asyncio
    async def test_proposal_generation_temporal(self, feedback_loop):
        """Test adaptation proposal generation for temporal patterns."""
        pattern = DetectedPattern(
            pattern_type=PatternType.TEMPORAL,
            pattern_id="tool_usage_by_hour",
            description="Different tools used at different times",
            evidence_nodes=["node1", "node2"],
            confidence=0.85,
            detected_at=datetime.now(timezone.utc),
            metrics={
                "morning_tools": ["research_tool", "analyzer"],
                "evening_tools": ["summary_tool", "reporter"]
            }
        )
        
        proposals = await feedback_loop._generate_proposals([pattern])
        
        assert len(proposals) == 1
        proposal = proposals[0]
        
        # Check proposal structure
        assert proposal.scope == GraphScope.LOCAL
        assert proposal.auto_applicable is True
        assert ConfigNodeType.TOOL_PREFERENCES.value in proposal.proposed_changes
        
        # Check proposed changes
        changes = proposal.proposed_changes[ConfigNodeType.TOOL_PREFERENCES.value]
        assert changes['time_based_selection'] is True
        assert 'morning_tools' in changes
        assert 'evening_tools' in changes
    
    @pytest.mark.asyncio
    async def test_proposal_generation_performance(self, feedback_loop):
        """Test adaptation proposal generation for performance issues."""
        pattern = DetectedPattern(
            pattern_type=PatternType.PERFORMANCE,
            pattern_id="perf_degradation_response_time",
            description="Response times degraded by 60%",
            evidence_nodes=["metric1", "metric2"],
            confidence=0.8,
            detected_at=datetime.now(timezone.utc),
            metrics={
                "degradation": 1.6  # 60% slower
            }
        )
        
        proposals = await feedback_loop._generate_proposals([pattern])
        
        assert len(proposals) == 1
        proposal = proposals[0]
        
        # Performance changes should require approval
        assert proposal.scope == GraphScope.IDENTITY
        assert proposal.auto_applicable is False
        assert ConfigNodeType.BEHAVIOR_CONFIG.value in proposal.proposed_changes
        
        # Check performance optimizations
        changes = proposal.proposed_changes[ConfigNodeType.BEHAVIOR_CONFIG.value]
        assert changes['enable_performance_mode'] is True
        assert 'timeout_adjustments' in changes
    
    @pytest.mark.asyncio
    async def test_auto_apply_local_changes(self, feedback_loop, mock_memory_bus):
        """Test automatic application of LOCAL scope changes."""
        proposal = AdaptationProposalNode(
            trigger="Test pattern",
            current_pattern="Old behavior",
            proposed_changes={
                ConfigNodeType.TOOL_PREFERENCES.value: {
                    "preferred_tool": "new_tool"
                }
            },
            evidence=["evidence1"],
            confidence=0.85,
            auto_applicable=True,
            scope=GraphScope.LOCAL
        )
        
        applied = await feedback_loop._apply_adaptations([proposal])
        
        assert len(applied) == 1
        assert applied[0] == proposal.id
        
        # Verify configuration was stored
        assert mock_memory_bus.memorize.called
        memorize_call = mock_memory_bus.memorize.call_args_list[0]
        config_node = memorize_call[1]['node']
        assert config_node.type == NodeType.CONFIG
        assert config_node.scope == GraphScope.LOCAL
    
    @pytest.mark.asyncio
    async def test_skip_low_confidence_proposals(self, feedback_loop):
        """Test that low confidence patterns don't generate proposals."""
        low_confidence_pattern = DetectedPattern(
            pattern_type=PatternType.TEMPORAL,
            pattern_id="weak_pattern",
            description="Weak correlation",
            evidence_nodes=[],
            confidence=0.5,  # Below threshold
            detected_at=datetime.now(timezone.utc),
            metrics={}
        )
        
        proposals = await feedback_loop._generate_proposals([low_confidence_pattern])
        assert len(proposals) == 0
    
    @pytest.mark.asyncio
    async def test_learning_state_tracking(self, feedback_loop, mock_memory_bus):
        """Test that learning state is properly tracked."""
        patterns = [
            DetectedPattern(
                pattern_type=PatternType.TEMPORAL,
                pattern_id="test_pattern",
                description="Test",
                evidence_nodes=[],
                confidence=0.8,
                detected_at=datetime.now(timezone.utc),
                metrics={}
            )
        ]
        
        await feedback_loop._update_learning_state(patterns, [], ["applied_1"])
        
        # Check history tracking
        assert len(feedback_loop._pattern_history) == 1
        assert len(feedback_loop._successful_adaptations) == 1
        
        # Verify learning summary was stored
        assert mock_memory_bus.memorize.called
        learning_call = mock_memory_bus.memorize.call_args
        learning_node = learning_call[1]['node']
        assert learning_node.attributes['patterns_detected'] == 1
        assert learning_node.attributes['total_successful_adaptations'] == 1
    
    @pytest.mark.asyncio
    async def test_analyze_and_adapt_full_cycle(self, feedback_loop, mock_memory_bus):
        """Test complete analysis and adaptation cycle."""
        # Mock data for full cycle
        mock_memory_bus.recall_timeseries.side_effect = [
            # For temporal patterns
            [{
                "id": "action_1",
                "timestamp": datetime.now(timezone.utc).replace(hour=9),
                "action_type": "TOOL",
                "tool_name": "morning_tool"
            }],
            # For frequency patterns
            [{"action_type": "SPEAK", "id": f"speak_{i}"} for i in range(10)],
            # For performance patterns
            [],
            # For error patterns
            []
        ]
        
        # Force analysis
        result = await feedback_loop.analyze_and_adapt(force=True)
        
        assert result['status'] == 'completed'
        assert result['patterns_detected'] >= 0
        assert 'timestamp' in result
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, feedback_loop):
        """Test service start/stop lifecycle."""
        await feedback_loop.start()
        assert await feedback_loop.is_healthy() is True
        
        # Stop should run final analysis
        with patch.object(feedback_loop, 'analyze_and_adapt') as mock_analyze:
            mock_analyze.return_value = {"status": "completed"}
            await feedback_loop.stop()
            mock_analyze.assert_called_once_with(force=True)
    
    def test_capabilities(self, feedback_loop):
        """Test service capabilities list."""
        capabilities = asyncio.run(feedback_loop.get_capabilities())
        expected = [
            "analyze_and_adapt", "detect_patterns", "generate_proposals",
            "apply_adaptations", "temporal_pattern_detection", "frequency_analysis",
            "performance_monitoring", "error_pattern_detection"
        ]
        assert set(capabilities) == set(expected)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, feedback_loop, mock_memory_bus):
        """Test error handling in pattern detection."""
        # Simulate memory bus error
        mock_memory_bus.recall_timeseries.side_effect = Exception("Memory error")
        
        patterns = await feedback_loop._detect_patterns()
        
        # Should return empty list on error
        assert patterns == []
    
    def test_pattern_history_limit(self, feedback_loop):
        """Test that pattern history is limited to prevent memory issues."""
        # Add many patterns
        for i in range(1500):
            pattern = DetectedPattern(
                pattern_type=PatternType.TEMPORAL,
                pattern_id=f"pattern_{i}",
                description="Test",
                evidence_nodes=[],
                confidence=0.8,
                detected_at=datetime.now(timezone.utc),
                metrics={}
            )
            feedback_loop._pattern_history.append(pattern)
        
        # Update should trim to last 1000
        asyncio.run(feedback_loop._update_learning_state([], [], []))
        assert len(feedback_loop._pattern_history) == 1000