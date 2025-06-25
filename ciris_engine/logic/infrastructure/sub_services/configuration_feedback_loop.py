"""
Configuration Feedback Loop Service

Implements the continuous feedback loop between metrics and configuration updates.
This enables autonomous adaptation based on observed patterns and performance.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from datetime import datetime, timedelta
from collections import defaultdict

from ciris_engine.protocols.services import Service

if TYPE_CHECKING:
    from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.infrastructure.feedback_loop import (
    PatternType, PatternMetrics, DetectedPattern, ConfigurationUpdate,
    AnalysisResult
)
from ciris_engine.schemas.services.nodes import ConfigChange, ConfigChangeType, ConfigValue
from ciris_engine.schemas.infrastructure.behavioral_patterns import ActionFrequency
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType, ConfigNodeType, CONFIG_SCOPE_MAP
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpStatus
from ciris_engine.schemas.runtime.memory import TimeSeriesDataPoint
from ciris_engine.logic.buses.memory_bus import MemoryBus

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

# PatternType now imported from schemas

# DetectedPattern now imported from schemas

# ConfigurationUpdate now imported from schemas

class ConfigurationFeedbackLoop(Service):
    """
    Service that creates a continuous feedback loop between system metrics
    and configuration updates.
    
    Flow: Metrics → Pattern Detection → Adaptation Proposals → Config Updates → New Behavior
    """
    
    def __init__(
        self,
        time_service: TimeServiceProtocol,
        memory_bus: Optional[MemoryBus] = None,
        pattern_threshold: float = 0.7,
        adaptation_threshold: float = 0.8,
        analysis_interval_hours: int = 6
    ) -> None:
        super().__init__()
        self._time_service = time_service
        self._memory_bus = memory_bus
        self._pattern_threshold = pattern_threshold
        self._adaptation_threshold = adaptation_threshold
        self._analysis_interval_hours = analysis_interval_hours
        
        # Pattern detection state
        self._detected_patterns: Dict[str, DetectedPattern] = {}
        self._last_analysis = self._time_service.now()
        
        # Learning state
        self._pattern_history: List[DetectedPattern] = []
        self._successful_adaptations: List[str] = []
        self._failed_adaptations: List[str] = []
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry for accessing memory bus."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.logic.buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
    
    async def analyze_and_adapt(self, force: bool = False) -> AnalysisResult:
        """
        Main entry point: Analyze metrics and create adaptation proposals.
        
        Args:
            force: Force analysis even if not due
            
        Returns:
            Summary of analysis and adaptations
        """
        try:
            # Check if analysis is due
            time_since_last = self._time_service.now() - self._last_analysis
            if not force and time_since_last.total_seconds() < self._analysis_interval_hours * 3600:
                return AnalysisResult(
                    status="not_due",
                    patterns_detected=0,
                    proposals_generated=0,
                    adaptations_applied=0,
                    timestamp=self._time_service.now(),
                    next_analysis_in=self._analysis_interval_hours * 3600 - time_since_last.total_seconds()
                )
            
            # 1. Detect patterns from recent metrics
            patterns = await self._detect_patterns()
            
            # 2. Generate adaptation proposals
            proposals = await self._generate_proposals(patterns)
            
            # 3. Apply eligible adaptations
            applied = await self._apply_adaptations(proposals)
            
            # 4. Update learning state
            await self._update_learning_state(patterns, proposals, applied)
            
            self._last_analysis = self._time_service.now()
            
            return AnalysisResult(
                status="completed",
                patterns_detected=len(patterns),
                proposals_generated=len(proposals),
                adaptations_applied=len(applied),
                timestamp=self._time_service.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze and adapt: {e}")
            return AnalysisResult(
                status="error",
                patterns_detected=0,
                proposals_generated=0,
                adaptations_applied=0,
                timestamp=self._time_service.now(),
                error=str(e)
            )
    
    async def _detect_patterns(self) -> List[DetectedPattern]:
        """Detect patterns from recent metrics and telemetry."""
        patterns = []
        
        try:
            # Detect temporal patterns
            temporal_patterns = await self._detect_temporal_patterns()
            patterns.extend(temporal_patterns)
            
            # Detect frequency patterns
            frequency_patterns = await self._detect_frequency_patterns()
            patterns.extend(frequency_patterns)
            
            # Detect performance patterns
            performance_patterns = await self._detect_performance_patterns()
            patterns.extend(performance_patterns)
            
            # Detect error patterns
            error_patterns = await self._detect_error_patterns()
            patterns.extend(error_patterns)
            
            # Store detected patterns
            for pattern in patterns:
                self._detected_patterns[pattern.pattern_id] = pattern
                await self._store_pattern(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect patterns: {e}")
            return []
    
    async def _detect_temporal_patterns(self) -> List[DetectedPattern]:
        """Detect time-based patterns in system behavior."""
        patterns = []
        
        try:
            # Query recent actions by hour
            actions_by_hour = await self._get_actions_by_hour()
            
            # Analyze tool usage patterns
            tool_patterns = self._analyze_tool_usage_by_time(actions_by_hour)
            patterns.extend(tool_patterns)
            
            # Analyze response time patterns
            response_patterns = await self._analyze_response_time_patterns()
            patterns.extend(response_patterns)
            
            # Analyze user interaction patterns
            interaction_patterns = await self._analyze_interaction_patterns()
            patterns.extend(interaction_patterns)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect temporal patterns: {e}")
            return []
    
    async def _detect_frequency_patterns(self) -> List[DetectedPattern]:
        """Detect patterns in usage frequency."""
        patterns = []
        
        try:
            # Analyze action frequency
            action_frequency = await self._get_action_frequency()
            
            # Detect dominant actions
            dominant_actions = self._find_dominant_actions(action_frequency)
            total_count = sum(af.count for af in action_frequency.values())
            for action, freq_data in dominant_actions.items():
                percentage = freq_data.count / max(1, total_count)
                pattern = DetectedPattern(
                    pattern_type=PatternType.FREQUENCY,
                    pattern_id=f"freq_dominant_{action}",
                    description=f"Action '{action}' is used {percentage:.1%} of the time",
                    evidence_nodes=freq_data.evidence[:10],  # Limit evidence
                    confidence=min(freq_data.count / 10.0, 1.0),  # Higher count = higher confidence
                    detected_at=self._time_service.now(),
                    metrics=PatternMetrics(
                        occurrence_count=freq_data.count,
                        average_value=percentage,
                        data_points=freq_data.count,
                        metadata={
                            "action": action,
                            "percentage": percentage
                        }
                    )
                )
                patterns.append(pattern)
            
            # Detect underused capabilities
            underused_capabilities = self._find_underused_capabilities(action_frequency)
            for capability in underused_capabilities:
                # Get the frequency data if it exists
                freq_data = action_frequency.get(capability)
                count = freq_data.count if freq_data else 0
                last_used = freq_data.last_seen if freq_data else None
                
                pattern = DetectedPattern(
                    pattern_type=PatternType.FREQUENCY,
                    pattern_id=f"freq_underused_{capability}",
                    description=f"Capability '{capability}' is rarely used ({count} times)",
                    evidence_nodes=[],
                    confidence=0.9,  # High confidence in counting
                    detected_at=self._time_service.now(),
                    metrics=PatternMetrics(
                        occurrence_count=count,
                        data_points=count,
                        metadata={
                            "capability": capability,
                            "last_used": last_used.isoformat() if last_used else None
                        }
                    )
                )
                patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect frequency patterns: {e}")
            return []
    
    async def _detect_performance_patterns(self) -> List[DetectedPattern]:
        """Detect patterns in system performance."""
        patterns = []
        
        try:
            # Query performance metrics
            if not self._memory_bus:
                return []
                
            performance_data = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=24 * 7,  # Last week
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="config_feedback_loop"
            )
            
            # Analyze response time trends
            response_times = [
                d for d in performance_data 
                if d.metric_name.endswith('response_time')
            ]
            
            if len(response_times) > 10:
                # Calculate trend
                times = [d.value for d in response_times[-20:]]
                avg_recent = sum(times[-10:]) / 10
                avg_previous = sum(times[:10]) / 10
                
                if avg_recent > avg_previous * 1.2:  # 20% slower
                    pattern = DetectedPattern(
                        pattern_type=PatternType.PERFORMANCE,
                        pattern_id="perf_degradation_response_time",
                        description=f"Response times degraded by {(avg_recent/avg_previous - 1)*100:.1f}%",
                        evidence_nodes=[str(d.timestamp) for d in response_times[-10:]],
                        confidence=0.8,
                        detected_at=self._time_service.now(),
                        metrics=PatternMetrics(
                            average_value=avg_recent,
                            peak_value=max(times[-10:]),
                            trend="increasing",
                            metadata={
                                "avg_previous": avg_previous,
                                "degradation": avg_recent / avg_previous
                            }
                        )
                    )
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect performance patterns: {e}")
            return []
    
    async def _detect_error_patterns(self) -> List[DetectedPattern]:
        """Detect patterns in errors and failures."""
        patterns = []
        
        try:
            # Query error logs
            if not self._memory_bus:
                return []
                
            error_data = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=24 * 3,  # Last 3 days
                correlation_types=["LOG_ENTRY"],
                handler_name="config_feedback_loop"
            )
            
            # Filter for errors
            errors = [
                d for d in error_data 
                if d.tags and d.tags.get('log_level') in ['ERROR', 'WARNING']
            ]
            
            # Group errors by type
            error_groups = defaultdict(list)
            for error in errors:
                error_type = self._extract_error_type(error)
                error_groups[error_type].append(error)
            
            # Find recurring errors
            for error_type, instances in error_groups.items():
                if len(instances) >= 3:  # At least 3 occurrences
                    pattern = DetectedPattern(
                        pattern_type=PatternType.ERROR,
                        pattern_id=f"error_recurring_{error_type}",
                        description=f"Recurring error: {error_type} ({len(instances)} times)",
                        evidence_nodes=[str(e.timestamp) for e in instances[:5]],
                        confidence=min(0.9, len(instances) / 10),  # Higher count = higher confidence
                        detected_at=self._time_service.now(),
                        metrics=PatternMetrics(
                            occurrence_count=len(instances),
                            data_points=len(instances),
                            metadata={
                                "error_type": error_type,
                                "first_seen": str(min(e.timestamp for e in instances)),
                                "last_seen": str(max(e.timestamp for e in instances))
                            }
                        )
                    )
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect error patterns: {e}")
            return []
    
    async def _store_pattern_insights(self, patterns: List[DetectedPattern]) -> int:
        """Store patterns as insight nodes for agent introspection."""
        if not self._memory_bus:
            return 0
        
        stored = 0
        for pattern in patterns:
            if pattern.confidence < self._pattern_threshold:
                continue
                
            try:
                insight_node = GraphNode(
                    id=f"insight_{pattern.pattern_id}_{int(self._time_service.now().timestamp())}",
                    type=NodeType.CONCEPT,
                    scope=GraphScope.LOCAL,
                    attributes={
                        "insight_type": "behavioral_pattern",
                        "pattern_type": pattern.pattern_type.value,
                        "description": pattern.description,
                        "confidence": pattern.confidence,
                        "evidence": pattern.evidence_nodes[:10],  # Limit evidence
                        "metrics": pattern.metrics.model_dump() if pattern.metrics else {},
                        "detected_at": pattern.detected_at.isoformat(),
                        "actionable": True  # Agent can act on this insight
                    }
                )
                
                await self._memory_bus.memorize(
                    node=insight_node,
                    handler_name="configuration_feedback_loop",
                    metadata={"source": "pattern_analysis"}
                )
                stored += 1
                
            except Exception as e:
                logger.error(f"Failed to store insight for pattern {pattern.pattern_id}: {e}")
                
        return stored
                            
    async def _update_learning_state(
        self,
        patterns: List[DetectedPattern]
    ) -> None:
        """Update our learning state based on results."""
        # Track pattern history
        self._pattern_history.extend(patterns)
        if len(self._pattern_history) > 1000:
            self._pattern_history = self._pattern_history[-1000:]  # Keep last 1000
        
        # Store learning summary
        learning_node = GraphNode(
            id=f"learning_state_{int(self._time_service.now().timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={
                "timestamp": self._time_service.now().isoformat(),
                "patterns_detected": len(patterns),
                "proposals_generated": 0,  # No longer generating proposals
                "adaptations_applied": 0,  # No longer applying adaptations,
                "total_successful_adaptations": len(self._successful_adaptations),
                "pattern_types_seen": list(set(p.pattern_type.value for p in patterns))
            }
        )
        
        if self._memory_bus:
            await self._memory_bus.memorize(
                node=learning_node,
                handler_name="config_feedback_loop",
                metadata={"learning_state": True}
            )
    
    # Helper methods
    
    async def _get_actions_by_hour(self) -> Dict[int, List[TimeSeriesDataPoint]]:
        """Get actions grouped by hour of day."""
        actions_by_hour: Dict[int, List[TimeSeriesDataPoint]] = defaultdict(list)
        
        # Query recent actions
        if not self._memory_bus:
            return {}
            
        action_data = await self._memory_bus.recall_timeseries(
            scope="local",
            hours=24 * 7,  # Last week
            correlation_types=["AUDIT_EVENT"],
            handler_name="config_feedback_loop"
        )
        
        for action in action_data:
            timestamp = action.timestamp
            
            hour = timestamp.hour
            actions_by_hour[hour].append(action)
        
        return dict(actions_by_hour)
    
    def _analyze_tool_usage_by_time(self, actions_by_hour: Dict[int, List[TimeSeriesDataPoint]]) -> List[DetectedPattern]:
        """Analyze tool usage patterns by time of day."""
        patterns = []
        
        # Extract tool usage by hour
        tools_by_hour: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        for hour, actions in actions_by_hour.items():
            for action in actions:
                # Check tags for action type
                if action.tags and action.tags.get('action') == 'TOOL':
                    tool_name = action.tags.get('tool_name', 'unknown')
                    tools_by_hour[hour][tool_name] += 1
        
        # Find patterns
        morning_tools: Dict[str, int] = defaultdict(int)
        evening_tools: Dict[str, int] = defaultdict(int)
        
        for hour, tools in tools_by_hour.items():
            if 6 <= hour < 12:  # Morning
                for tool, count in tools.items():
                    morning_tools[tool] += count
            elif 18 <= hour < 23:  # Evening
                for tool, count in tools.items():
                    evening_tools[tool] += count
        
        # Check if there's a significant difference
        if morning_tools and evening_tools:
            # Get top tools for each period
            top_morning = sorted(morning_tools.items(), key=lambda x: x[1], reverse=True)[:3]
            top_evening = sorted(evening_tools.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Check if they're different
            morning_set = set(tool for tool, _ in top_morning)
            evening_set = set(tool for tool, _ in top_evening)
            
            if morning_set != evening_set:
                pattern = DetectedPattern(
                    pattern_type=PatternType.TEMPORAL,
                    pattern_id="tool_usage_by_hour",
                    description="Different tools preferred at different times of day",
                    evidence_nodes=[],
                    confidence=0.8,
                    detected_at=self._time_service.now(),
                    metrics=PatternMetrics(
                        metadata={
                            "morning_tools": [tool for tool, _ in top_morning],
                            "evening_tools": [tool for tool, _ in top_evening]
                        }
                    )
                )
                patterns.append(pattern)
        
        return patterns
    
    async def _analyze_response_time_patterns(self) -> List[DetectedPattern]:
        """Analyze response time patterns."""
        # This would analyze response times by various factors
        # For now, returning empty list
        return []
    
    async def _analyze_interaction_patterns(self) -> List[DetectedPattern]:
        """Analyze user interaction patterns."""
        # This would analyze how users interact with the agent
        # For now, returning empty list
        return []
    
    async def _get_action_frequency(self) -> Dict[str, ActionFrequency]:
        """Get frequency of different actions."""
        action_data_raw: Dict[str, dict] = defaultdict(lambda: {"count": 0, "evidence": [], "last_seen": None})
        
        # Query recent actions
        if not self._memory_bus:
            return {}
            
        action_data = await self._memory_bus.recall_timeseries(
            scope="local",
            hours=24 * 7,  # Last week
            correlation_types=["AUDIT_EVENT"],
            handler_name="config_feedback_loop"
        )
        
        for action in action_data:
            # Extract action type from tags
            action_type = action.tags.get('action', 'unknown') if action.tags else 'unknown'
            action_data_raw[action_type]["count"] += 1
            
            # Track last seen
            action_time = datetime.fromisoformat(action.timestamp)
            if action_data_raw[action_type]["last_seen"] is None or action_time > action_data_raw[action_type]["last_seen"]:
                action_data_raw[action_type]["last_seen"] = action_time
            
            # Use correlation_id as evidence (limit to 10)
            if hasattr(action, 'correlation_id') and action.correlation_id and len(action_data_raw[action_type]["evidence"]) < 10:
                action_data_raw[action_type]["evidence"].append(f"Action {action.correlation_id} at {action.timestamp}")
        
        # Convert to ActionFrequency objects
        action_frequency: Dict[str, ActionFrequency] = {}
        total_days = 7  # We queried last 7 days
        
        for action_type, data in action_data_raw.items():
            if data["count"] > 0:
                action_frequency[action_type] = ActionFrequency(
                    action=action_type,
                    count=data["count"],
                    evidence=data["evidence"],
                    last_seen=data["last_seen"] or self._time_service.now(),
                    daily_average=data["count"] / total_days
                )
        
        return action_frequency
    
    def _find_dominant_actions(self, action_frequency: Dict[str, ActionFrequency]) -> Dict[str, ActionFrequency]:
        """Find actions that dominate usage."""
        dominant = {}
        
        # Calculate total actions
        total_count = sum(af.count for af in action_frequency.values())
        
        for action, freq_data in action_frequency.items():
            percentage = freq_data.count / max(1, total_count)
            if percentage > 0.3:  # More than 30% of actions
                dominant[action] = freq_data
        
        return dominant
    
    def _find_underused_capabilities(self, action_frequency: Dict[str, ActionFrequency]) -> List[str]:
        """Find capabilities that are rarely used."""
        # Define expected capabilities
        expected_capabilities = [
            "OBSERVE", "SPEAK", "TOOL", "MEMORIZE", "RECALL", 
            "FORGET", "DEFER", "REJECT", "PONDER", "TASK_COMPLETE"
        ]
        
        underused = []
        for capability in expected_capabilities:
            # Check if capability is missing or rarely used (less than 5 times in a week)
            if capability not in action_frequency or action_frequency[capability].count < 5:
                underused.append(capability)
        
        return underused
    
    def _extract_error_type(self, error_data: TimeSeriesDataPoint) -> str:
        """Extract error type from error data."""
        # Simple extraction - could be more sophisticated
        tags = error_data.tags or {}
        if 'error_type' in tags:
            error_type = tags['error_type']
            return str(error_type) if error_type else 'unknown_error'
        
        # Try to extract from metric name
        if 'timeout' in error_data.metric_name.lower():
            return 'timeout_error'
        elif 'tool' in error_data.metric_name.lower():
            return 'tool_error'
        elif 'memory' in error_data.metric_name.lower():
            return 'memory_error'
        else:
            return 'unknown_error'
    
    def _extract_tool_name(self, error_type: str) -> Optional[str]:
        """Extract tool name from error type."""
        # Simple extraction - could be more sophisticated
        parts = error_type.split('_')
        if len(parts) > 2 and parts[0] == 'tool':
            return parts[1]
        return None
    
    async def _store_pattern(self, pattern: DetectedPattern) -> None:
        """Store a detected pattern in memory."""
        pattern_node = GraphNode(
            id=f"pattern_{pattern.pattern_id}_{int(pattern.detected_at.timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={
                "pattern_type": pattern.pattern_type.value,
                "pattern_id": pattern.pattern_id,
                "description": pattern.description,
                "confidence": pattern.confidence,
                "detected_at": pattern.detected_at.isoformat(),
                "metrics": pattern.metrics,
                "evidence_count": len(pattern.evidence_nodes)
            }
        )
        
        if self._memory_bus:
            await self._memory_bus.memorize(
                node=pattern_node,
                handler_name="config_feedback_loop",
                metadata={"detected_pattern": True}
            )
    
    async def start(self) -> None:
        """Start the configuration feedback loop."""
        logger.info("ConfigurationFeedbackLoop started - enabling autonomous adaptation")
    
    async def stop(self) -> None:
        """Stop the feedback loop."""
        # Run final analysis
        try:
            await self.analyze_and_adapt(force=True)
        except Exception as e:
            logger.error(f"Failed final analysis: {e}")
        
        logger.info("ConfigurationFeedbackLoop stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self._memory_bus is not None
    
    def get_capabilities(self) -> "ServiceCapabilities":
        """Get service capabilities."""
        from ciris_engine.schemas.services.core import ServiceCapabilities
        return ServiceCapabilities(
            service_name="ConfigurationFeedbackLoop",
            actions=[
                "analyze_and_adapt", 
                "detect_patterns", 
                "store_insights", 
                "temporal_pattern_detection", 
                "frequency_analysis",
                "performance_monitoring", 
                "error_pattern_detection"
            ],
            version="1.0.0",
            dependencies=["TimeService", "MemoryBus"],
            metadata={
                "pattern_threshold": self.pattern_threshold,
                "adaptation_threshold": self.adaptation_threshold,
                "analysis_interval_hours": self.analysis_interval_hours
            }
        )
    
    def get_status(self) -> "ServiceStatus":
        """Get current service status."""
        from ciris_engine.schemas.services.core import ServiceStatus
        return ServiceStatus(
            service_name="ConfigurationFeedbackLoop",
            service_type="infrastructure_sub_service",
            is_healthy=self._memory_bus is not None,
            uptime_seconds=0.0,  # Not tracking uptime for sub-services
            metrics={
                "pattern_threshold": self.pattern_threshold,
                "adaptation_threshold": self.adaptation_threshold,
                "patterns_detected": float(len(self.detected_patterns))
            },
            last_error=None,
            last_health_check=self._time_service.now() if self._time_service else None
        )
