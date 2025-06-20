"""
Configuration Feedback Loop Service

Implements the continuous feedback loop between metrics and configuration updates.
This enables autonomous adaptation based on observed patterns and performance.
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from ciris_engine.protocols.services import Service
from ciris_engine.schemas.graph_schemas_v1 import (
    GraphNode, GraphScope, NodeType, ConfigNodeType, 
    CONFIG_SCOPE_MAP, AdaptationProposalNode
)
from ciris_engine.schemas.memory_schemas_v1 import MemoryQuery, MemoryOpStatus
from ciris_engine.schemas.protocol_schemas_v1 import TimeSeriesDataPoint
from ciris_engine.message_buses.memory_bus import MemoryBus

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Types of patterns we can detect."""
    TEMPORAL = "temporal"          # Time-based patterns
    FREQUENCY = "frequency"        # Usage frequency patterns
    PERFORMANCE = "performance"    # Performance optimization patterns
    ERROR = "error"               # Error/failure patterns
    USER_PREFERENCE = "user_preference"  # User interaction patterns


@dataclass
class DetectedPattern:
    """A pattern detected from metrics/telemetry."""
    pattern_type: PatternType
    pattern_id: str
    description: str
    evidence_nodes: List[str]
    confidence: float
    detected_at: datetime
    metrics: Dict[str, Any]


@dataclass
class ConfigurationUpdate:
    """A configuration update derived from patterns."""
    config_type: ConfigNodeType
    update_type: str  # "create", "modify", "delete"
    current_value: Any
    new_value: Any
    reason: str
    pattern_id: str
    applied: bool = False


class ConfigurationFeedbackLoop(Service):
    """
    Service that creates a continuous feedback loop between system metrics
    and configuration updates.
    
    Flow: Metrics → Pattern Detection → Adaptation Proposals → Config Updates → New Behavior
    """
    
    def __init__(
        self,
        memory_bus: Optional[MemoryBus] = None,
        pattern_threshold: float = 0.7,
        adaptation_threshold: float = 0.8,
        analysis_interval_hours: int = 6
    ) -> None:
        super().__init__()
        self._memory_bus = memory_bus
        self._pattern_threshold = pattern_threshold
        self._adaptation_threshold = adaptation_threshold
        self._analysis_interval_hours = analysis_interval_hours
        
        # Pattern detection state
        self._detected_patterns: Dict[str, DetectedPattern] = {}
        self._last_analysis = datetime.now(timezone.utc)
        
        # Learning state
        self._pattern_history: List[DetectedPattern] = []
        self._successful_adaptations: List[str] = []
        self._failed_adaptations: List[str] = []
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry for accessing memory bus."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.message_buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
    
    async def analyze_and_adapt(self, force: bool = False) -> Dict[str, Any]:
        """
        Main entry point: Analyze metrics and create adaptation proposals.
        
        Args:
            force: Force analysis even if not due
            
        Returns:
            Summary of analysis and adaptations
        """
        try:
            # Check if analysis is due
            time_since_last = datetime.now(timezone.utc) - self._last_analysis
            if not force and time_since_last.total_seconds() < self._analysis_interval_hours * 3600:
                return {"status": "not_due", "next_analysis_in": self._analysis_interval_hours * 3600 - time_since_last.total_seconds()}
            
            # 1. Detect patterns from recent metrics
            patterns = await self._detect_patterns()
            
            # 2. Generate adaptation proposals
            proposals = await self._generate_proposals(patterns)
            
            # 3. Apply eligible adaptations
            applied = await self._apply_adaptations(proposals)
            
            # 4. Update learning state
            await self._update_learning_state(patterns, proposals, applied)
            
            self._last_analysis = datetime.now(timezone.utc)
            
            return {
                "status": "completed",
                "patterns_detected": len(patterns),
                "proposals_generated": len(proposals),
                "adaptations_applied": len(applied),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze and adapt: {e}")
            return {"status": "error", "error": str(e)}
    
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
            for action, data in dominant_actions.items():
                pattern = DetectedPattern(
                    pattern_type=PatternType.FREQUENCY,
                    pattern_id=f"freq_dominant_{action}",
                    description=f"Action '{action}' is used {data['percentage']:.1%} of the time",
                    evidence_nodes=data['evidence'][:10],  # Limit evidence
                    confidence=data['confidence'],
                    detected_at=datetime.now(timezone.utc),
                    metrics={
                        "action": action,
                        "count": data['count'],
                        "percentage": data['percentage']
                    }
                )
                patterns.append(pattern)
            
            # Detect underused capabilities
            underused = self._find_underused_capabilities(action_frequency)
            for capability, data in underused.items():
                pattern = DetectedPattern(
                    pattern_type=PatternType.FREQUENCY,
                    pattern_id=f"freq_underused_{capability}",
                    description=f"Capability '{capability}' is rarely used ({data['count']} times)",
                    evidence_nodes=[],
                    confidence=0.9,  # High confidence in counting
                    detected_at=datetime.now(timezone.utc),
                    metrics={
                        "capability": capability,
                        "count": data['count'],
                        "last_used": data.get('last_used')
                    }
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
                        detected_at=datetime.now(timezone.utc),
                        metrics={
                            "avg_recent": avg_recent,
                            "avg_previous": avg_previous,
                            "degradation": avg_recent / avg_previous
                        }
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
                        detected_at=datetime.now(timezone.utc),
                        metrics={
                            "error_type": error_type,
                            "count": len(instances),
                            "first_seen": min(e.timestamp for e in instances),
                            "last_seen": max(e.timestamp for e in instances)
                        }
                    )
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect error patterns: {e}")
            return []
    
    async def _generate_proposals(self, patterns: List[DetectedPattern]) -> List[AdaptationProposalNode]:
        """Generate adaptation proposals based on detected patterns."""
        proposals = []
        
        for pattern in patterns:
            if pattern.confidence < self._pattern_threshold:
                continue
            
            # Generate proposals based on pattern type
            if pattern.pattern_type == PatternType.TEMPORAL:
                proposal = self._propose_temporal_adaptation(pattern)
            elif pattern.pattern_type == PatternType.FREQUENCY:
                proposal = self._propose_frequency_adaptation(pattern)
            elif pattern.pattern_type == PatternType.PERFORMANCE:
                proposal = self._propose_performance_adaptation(pattern)
            elif pattern.pattern_type == PatternType.ERROR:
                proposal = self._propose_error_adaptation(pattern)
            else:
                proposal = None
            
            if proposal:
                proposals.append(proposal)
        
        return proposals
    
    def _propose_temporal_adaptation(self, pattern: DetectedPattern) -> Optional[AdaptationProposalNode]:
        """Propose adaptation for temporal patterns."""
        if "tool_usage_by_hour" in pattern.pattern_id:
            # Extract hour ranges and tools
            metrics = pattern.metrics
            morning_tools = metrics.get('morning_tools', [])
            evening_tools = metrics.get('evening_tools', [])
            
            if morning_tools or evening_tools:
                return AdaptationProposalNode(
                    trigger=f"Temporal pattern: {pattern.description}",
                    current_pattern="Static tool preferences",
                    proposed_changes={
                        ConfigNodeType.TOOL_PREFERENCES.value: {
                            "time_based_selection": True,
                            "morning_tools": morning_tools,
                            "evening_tools": evening_tools,
                            "morning_hours": [6, 7, 8, 9, 10, 11],
                            "evening_hours": [18, 19, 20, 21, 22]
                        }
                    },
                    evidence=pattern.evidence_nodes,
                    confidence=pattern.confidence,
                    auto_applicable=True,  # Tool preferences are LOCAL scope
                    scope=GraphScope.LOCAL
                )
        
        return None
    
    def _propose_frequency_adaptation(self, pattern: DetectedPattern) -> Optional[AdaptationProposalNode]:
        """Propose adaptation for frequency patterns."""
        if "dominant" in pattern.pattern_id:
            action = pattern.metrics.get('action')
            percentage = pattern.metrics.get('percentage', 0)
            
            if percentage > 0.5:  # More than 50% of actions
                return AdaptationProposalNode(
                    trigger=f"Frequency pattern: {pattern.description}",
                    current_pattern=f"No optimization for {action}",
                    proposed_changes={
                        ConfigNodeType.RESPONSE_TEMPLATES.value: {
                            f"optimize_for_{action}": True,
                            f"{action}_cache_size": 100,
                            f"{action}_preload": True
                        }
                    },
                    evidence=pattern.evidence_nodes,
                    confidence=pattern.confidence,
                    auto_applicable=True,
                    scope=GraphScope.LOCAL
                )
        
        elif "underused" in pattern.pattern_id:
            capability = pattern.metrics.get('capability')
            count = pattern.metrics.get('count', 0)
            
            if count == 0:  # Never used
                return AdaptationProposalNode(
                    trigger=f"Underused capability: {pattern.description}",
                    current_pattern=f"Capability {capability} available but unused",
                    proposed_changes={
                        ConfigNodeType.CAPABILITY_LIMITS.value: {
                            f"disable_{capability}": True,
                            "reason": "Never used in practice"
                        }
                    },
                    evidence=[],
                    confidence=0.7,  # Lower confidence for removal
                    auto_applicable=False,  # Capability changes need approval
                    scope=GraphScope.IDENTITY
                )
        
        return None
    
    def _propose_performance_adaptation(self, pattern: DetectedPattern) -> Optional[AdaptationProposalNode]:
        """Propose adaptation for performance patterns."""
        if "degradation" in pattern.pattern_id:
            degradation = pattern.metrics.get('degradation', 1.0)
            
            if degradation > 1.5:  # More than 50% slower
                return AdaptationProposalNode(
                    trigger=f"Performance issue: {pattern.description}",
                    current_pattern="Performance degrading over time",
                    proposed_changes={
                        ConfigNodeType.BEHAVIOR_CONFIG.value: {
                            "enable_performance_mode": True,
                            "reduce_pondering_depth": True,
                            "cache_aggressive": True,
                            "timeout_adjustments": {
                                "tool_timeout": 0.8,  # 20% faster timeout
                                "llm_timeout": 0.9    # 10% faster timeout
                            }
                        }
                    },
                    evidence=pattern.evidence_nodes,
                    confidence=pattern.confidence * 0.8,  # Slightly lower for performance changes
                    auto_applicable=False,  # Behavior changes need approval
                    scope=GraphScope.IDENTITY
                )
        
        return None
    
    def _propose_error_adaptation(self, pattern: DetectedPattern) -> Optional[AdaptationProposalNode]:
        """Propose adaptation for error patterns."""
        error_type = pattern.metrics.get('error_type', '')
        count = pattern.metrics.get('count', 0)
        
        if count >= 5:  # Significant recurring error
            if "timeout" in error_type.lower():
                return AdaptationProposalNode(
                    trigger=f"Recurring error: {pattern.description}",
                    current_pattern=f"Frequent {error_type} errors",
                    proposed_changes={
                        ConfigNodeType.BEHAVIOR_CONFIG.value: {
                            "timeout_adjustments": {
                                "global_multiplier": 1.5,  # 50% more time
                                "retry_on_timeout": True,
                                "max_retries": 2
                            }
                        }
                    },
                    evidence=pattern.evidence_nodes,
                    confidence=pattern.confidence,
                    auto_applicable=False,
                    scope=GraphScope.IDENTITY
                )
            
            elif "tool" in error_type.lower():
                # Extract tool name if possible
                tool_name = self._extract_tool_name(error_type)
                if tool_name:
                    return AdaptationProposalNode(
                        trigger=f"Tool errors: {pattern.description}",
                        current_pattern=f"Tool {tool_name} failing frequently",
                        proposed_changes={
                            ConfigNodeType.TOOL_PREFERENCES.value: {
                                f"deprioritize_{tool_name}": True,
                                f"{tool_name}_reliability_score": 0.3,
                                "prefer_alternatives_to": [tool_name]
                            }
                        },
                        evidence=pattern.evidence_nodes,
                        confidence=pattern.confidence,
                        auto_applicable=True,
                        scope=GraphScope.LOCAL
                    )
        
        return None
    
    async def _apply_adaptations(self, proposals: List[AdaptationProposalNode]) -> List[str]:
        """Apply eligible adaptation proposals."""
        applied = []
        
        for proposal in proposals:
            try:
                # Check if proposal can be auto-applied
                if proposal.can_auto_apply(self._adaptation_threshold):
                    # Apply the configuration changes
                    success = await self._apply_configuration_changes(proposal)
                    
                    if success:
                        # Mark proposal as applied
                        proposal.applied = True
                        proposal.applied_at = datetime.now(timezone.utc)
                        
                        # Update proposal in memory
                        if self._memory_bus:
                            await self._memory_bus.memorize(
                                node=proposal,
                                handler_name="config_feedback_loop",
                                metadata={"applied": True}
                            )
                        
                        applied.append(proposal.id)
                        logger.info(f"Applied adaptation: {proposal.id}")
                else:
                    # Store proposal for manual review
                    if self._memory_bus:
                        await self._memory_bus.memorize(
                            node=proposal,
                            handler_name="config_feedback_loop",
                            metadata={"requires_review": True}
                        )
                    logger.info(f"Stored adaptation proposal for review: {proposal.id}")
                    
            except Exception as e:
                logger.error(f"Failed to apply adaptation {proposal.id}: {e}")
        
        return applied
    
    async def _apply_configuration_changes(self, proposal: AdaptationProposalNode) -> bool:
        """Apply the configuration changes from a proposal."""
        try:
            for config_type_str, changes in proposal.proposed_changes.items():
                # Get the config type enum
                config_type = ConfigNodeType(config_type_str)
                scope = CONFIG_SCOPE_MAP[config_type]
                
                # Create or update config node
                config_node = GraphNode(
                    id=f"config/{config_type.value}/adapted_{int(datetime.now(timezone.utc).timestamp())}",
                    type=NodeType.CONFIG,
                    scope=scope,
                    attributes={
                        "config_type": config_type.value,
                        "values": changes,
                        "source": "configuration_feedback_loop",
                        "proposal_id": proposal.id,
                        "applied_at": datetime.now(timezone.utc).isoformat()
                    }
                )
                
                # Store the configuration
                if not self._memory_bus:
                    return False
                    
                result = await self._memory_bus.memorize(
                    node=config_node,
                    handler_name="config_feedback_loop",
                    metadata={"configuration_update": True}
                )
                
                if result.status != MemoryOpStatus.OK:
                    logger.error(f"Failed to store config update: {result.error}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply configuration changes: {e}")
            return False
    
    async def _update_learning_state(
        self, 
        patterns: List[DetectedPattern],
        proposals: List[AdaptationProposalNode],
        applied: List[str]
    ) -> None:
        """Update our learning state based on results."""
        # Track pattern history
        self._pattern_history.extend(patterns)
        if len(self._pattern_history) > 1000:
            self._pattern_history = self._pattern_history[-1000:]  # Keep last 1000
        
        # Track successful adaptations
        self._successful_adaptations.extend(applied)
        
        # Store learning summary
        learning_node = GraphNode(
            id=f"learning_state_{int(datetime.now(timezone.utc).timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "patterns_detected": len(patterns),
                "proposals_generated": len(proposals),
                "adaptations_applied": len(applied),
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
                    detected_at=datetime.now(timezone.utc),
                    metrics={
                        "morning_tools": [tool for tool, _ in top_morning],
                        "evening_tools": [tool for tool, _ in top_evening]
                    }
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
    
    async def _get_action_frequency(self) -> Dict[str, Dict[str, Any]]:
        """Get frequency of different actions."""
        action_frequency: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "evidence": []})
        
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
            action_frequency[action_type]["count"] += 1
            # Use correlation_id as evidence
            if hasattr(action, 'correlation_id') and action.correlation_id:
                action_frequency[action_type]["evidence"].append(action.correlation_id)
        
        # Calculate percentages
        total = sum(data["count"] for data in action_frequency.values())
        for action_type, data in action_frequency.items():
            data["percentage"] = data["count"] / max(1, total)
            data["confidence"] = min(0.9, data["count"] / 100)  # More data = higher confidence
        
        return dict(action_frequency)
    
    def _find_dominant_actions(self, action_frequency: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Find actions that dominate usage."""
        dominant = {}
        
        for action, data in action_frequency.items():
            if data["percentage"] > 0.3:  # More than 30% of actions
                dominant[action] = data
        
        return dominant
    
    def _find_underused_capabilities(self, action_frequency: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Find capabilities that are rarely used."""
        # Define expected capabilities
        expected_capabilities = [
            "OBSERVE", "SPEAK", "TOOL", "MEMORIZE", "RECALL", 
            "FORGET", "DEFER", "REJECT", "PONDER", "TASK_COMPLETE"
        ]
        
        underused = {}
        for capability in expected_capabilities:
            if capability not in action_frequency or action_frequency[capability]["count"] < 5:
                underused[capability] = action_frequency.get(
                    capability, 
                    {"count": 0, "percentage": 0, "evidence": []}
                )
        
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
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "analyze_and_adapt", "detect_patterns", "generate_proposals",
            "apply_adaptations", "temporal_pattern_detection", "frequency_analysis",
            "performance_monitoring", "error_pattern_detection"
        ]