"""
Self-Configuration Service

Orchestrates all self-configuration components to enable autonomous adaptation
within safe ethical boundaries. This is the master coordinator that ties together:
- IdentityVarianceMonitor (tracks drift from baseline)
- ConfigurationFeedbackLoop (detects patterns and stores insights)
- UnifiedTelemetryService (provides the data flow)

Together, these enable the agent to learn and adapt while maintaining its core identity.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry
from ciris_engine.schemas.services.special.self_configuration import (
    AdaptationCycleResult, CycleEventData, AdaptationStatus,
    ReviewOutcome, ObservabilityAnalysis,
    AdaptationOpportunity, AdaptationEffectiveness,
    PatternLibrarySummary, ServiceImprovementReport
)
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ciris_engine.logic.adapters.base import Service
from ciris_engine.protocols.services import SelfConfigurationServiceProtocol
from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.runtime.core import AgentIdentityRoot
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.logic.infrastructure.sub_services.identity_variance_monitor import IdentityVarianceMonitor
from ciris_engine.logic.infrastructure.sub_services.configuration_feedback_loop import ConfigurationFeedbackLoop
from ciris_engine.logic.services.graph.telemetry_service import GraphTelemetryService
from ciris_engine.logic.buses.memory_bus import MemoryBus

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

class AdaptationState(str, Enum):
    """Current state of the self-configuration system."""
    LEARNING = "learning"          # Gathering data, no changes yet
    PROPOSING = "proposing"        # Actively proposing adaptations
    ADAPTING = "adapting"          # Applying approved changes
    STABILIZING = "stabilizing"    # Waiting for changes to settle
    REVIEWING = "reviewing"        # Under WA review for variance

@dataclass
class AdaptationCycle:
    """Represents one complete adaptation cycle."""
    cycle_id: str
    started_at: datetime
    state: AdaptationState
    patterns_detected: int
    proposals_generated: int
    changes_applied: int
    variance_before: float
    variance_after: Optional[float]
    completed_at: Optional[datetime]

class SelfConfigurationService(Service, SelfConfigurationServiceProtocol, ServiceProtocol):
    """
    Master service that orchestrates self-configuration and autonomous adaptation.

    This service:
    1. Coordinates between variance monitoring, pattern detection, and telemetry
    2. Manages the adaptation lifecycle with safety checks
    3. Ensures changes stay within the 20% identity variance threshold
    4. Provides a unified interface for self-configuration

    The flow:
    Experience → Telemetry → Patterns → Insights → Agent Decisions → Config Changes
    """

    def __init__(
        self,
        time_service: TimeServiceProtocol,
        memory_bus: Optional[MemoryBus] = None,
        variance_threshold: float = 0.20,
        adaptation_interval_hours: int = 6,
        stabilization_period_hours: int = 24
    ) -> None:
        super().__init__()
        self._time_service = time_service
        self._memory_bus = memory_bus
        self._variance_threshold = variance_threshold
        self._adaptation_interval = timedelta(hours=adaptation_interval_hours)
        self._stabilization_period = timedelta(hours=stabilization_period_hours)

        # Component services
        self._variance_monitor: Optional[IdentityVarianceMonitor] = None
        self._feedback_loop: Optional[ConfigurationFeedbackLoop] = None
        self._telemetry_service: Optional[GraphTelemetryService] = None

        # State tracking
        self._current_state = AdaptationState.LEARNING
        self._current_cycle: Optional[AdaptationCycle] = None
        self._adaptation_history: List[AdaptationCycle] = []
        self._last_adaptation = self._time_service.now()
        # No more pending proposals - agent decides through thoughts

        # Safety mechanisms
        self._emergency_stop = False
        self._consecutive_failures = 0
        self._max_failures = 3

    def _set_service_registry(self, registry: "ServiceRegistry") -> None:
        """Set the service registry and initialize component services."""
        self._service_registry = registry

        # Initialize memory bus
        if not self._memory_bus and registry:
            try:
                from ciris_engine.logic.buses import MemoryBus
                self._memory_bus = MemoryBus(registry, self._time_service)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")

        # Initialize component services
        self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize the component services."""
        try:
            # Create variance monitor
            self._variance_monitor = IdentityVarianceMonitor(
                time_service=self._time_service,
                memory_bus=self._memory_bus,
                variance_threshold=self._variance_threshold
            )
            if self._service_registry:
                self._variance_monitor.set_service_registry(self._service_registry)

            # Create feedback loop
            self._feedback_loop = ConfigurationFeedbackLoop(
                time_service=self._time_service,
                memory_bus=self._memory_bus,
                analysis_interval_hours=int(self._adaptation_interval.total_seconds() / 3600)
            )
            if self._service_registry:
                self._feedback_loop.set_service_registry(self._service_registry)

            # Create telemetry service
            self._telemetry_service = GraphTelemetryService(
                memory_bus=self._memory_bus
            )
            if self._service_registry:
                self._telemetry_service._set_service_registry(self._service_registry)

            logger.info("Self-configuration components initialized")

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")

    async def _initialize_identity_baseline(self, identity: AgentIdentityRoot) -> str:
        """
        Initialize the identity baseline for variance monitoring.

        This should be called once during agent initialization.
        """
        if not self._variance_monitor:
            raise RuntimeError("Variance monitor not initialized")

        baseline_id = await self._variance_monitor.initialize_baseline(identity)
        logger.info(f"Identity baseline established: {baseline_id}")

        # Store initialization event
        init_node = GraphNode(
            id=f"self_config_init_{int(self._time_service.now().timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "event_type": "self_configuration_initialized",
                "baseline_id": baseline_id,
                "variance_threshold": self._variance_threshold,
                "timestamp": self._time_service.now().isoformat()
            }
        )

        if self._memory_bus:
            await self._memory_bus.memorize(init_node, handler_name="self_configuration")

        return baseline_id


    async def _should_run_adaptation_cycle(self) -> bool:
        """Check if it's time to run an adaptation cycle."""
        # Don't run if in emergency stop
        if self._emergency_stop:
            return False

        # Don't run if currently in a cycle
        if self._current_cycle and not self._current_cycle.completed_at:
            return False

        # Check state-based conditions
        if self._current_state == AdaptationState.REVIEWING:
            # Wait for WA review to complete
            return False

        if self._current_state == AdaptationState.STABILIZING:
            # Check if stabilization period has passed
            time_since_last = self._time_service.now() - self._last_adaptation
            if time_since_last < self._stabilization_period:
                return False

        # Check interval
        time_since_last = self._time_service.now() - self._last_adaptation
        return time_since_last >= self._adaptation_interval

    async def _run_adaptation_cycle(self) -> AdaptationCycleResult:
        """
        Run a variance check cycle.

        This method now only checks variance and triggers WA review if needed.
        Actual configuration changes happen through agent decisions.
        """
        try:
            # Check current variance
            if self._variance_monitor:
                variance_report = await self._variance_monitor.check_variance()
            else:
                return AdaptationCycleResult(
                    cycle_id="no_monitor",
                    state=self._current_state,
                    started_at=self._time_service.now(),
                    completed_at=self._time_service.now(),
                    patterns_detected=0,
                    proposals_generated=0,
                    changes_applied=0,
                    variance_before=0.0,
                    variance_after=0.0,
                    success=False,
                    error="Variance monitor not initialized"
                )

            cycle_id = f"variance_check_{int(self._time_service.now().timestamp())}"

            if variance_report.requires_wa_review:
                # Variance too high - enter review state
                self._current_state = AdaptationState.REVIEWING
                await self._store_cycle_event("variance_exceeded", {
                    "variance": variance_report.total_variance,
                    "threshold": self._variance_threshold
                })

            return AdaptationCycleResult(
                cycle_id=cycle_id,
                state=self._current_state,
                started_at=self._time_service.now(),
                completed_at=self._time_service.now(),
                patterns_detected=0,  # Patterns detected by feedback loop
                proposals_generated=0,  # No proposals - agent decides
                changes_applied=0,  # Changes via MEMORIZE
                variance_before=variance_report.total_variance,
                variance_after=variance_report.total_variance,
                success=True
            )

        except Exception as e:
            logger.error(f"Variance check failed: {e}")
            self._consecutive_failures += 1

            if self._consecutive_failures >= self._max_failures:
                self._emergency_stop = True
                logger.error("Emergency stop activated after repeated failures")

            return AdaptationCycleResult(
                cycle_id="error",
                state=self._current_state,
                started_at=self._time_service.now(),
                completed_at=self._time_service.now(),
                success=False,
                error=str(e)
            )


    async def _store_cycle_event(self, event_type: str, data: CycleEventData) -> None:
        """Store an event during the adaptation cycle."""
        cycle_id = self._current_cycle.cycle_id if self._current_cycle else "unknown"
        event_node = GraphNode(
            id=f"cycle_event_{cycle_id}_{event_type}_{int(self._time_service.now().timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={
                "cycle_id": cycle_id,
                "event_type": event_type,
                "data": data,
                "timestamp": self._time_service.now().isoformat()
            }
        )

        if self._memory_bus:
            await self._memory_bus.memorize(event_node, handler_name="self_configuration")

    async def _store_cycle_summary(self, cycle: AdaptationCycle) -> None:
        """Store a summary of the completed adaptation cycle."""
        summary_node = GraphNode(
            id=f"cycle_summary_{cycle.cycle_id}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "cycle_id": cycle.cycle_id,
                "duration_seconds": (cycle.completed_at - cycle.started_at).total_seconds() if cycle.completed_at else 0,
                "patterns_detected": cycle.patterns_detected,
                "proposals_generated": cycle.proposals_generated,
                "changes_applied": cycle.changes_applied,
                "variance_before": cycle.variance_before,
                "variance_after": cycle.variance_after,
                "final_state": cycle.state.value,
                "success": cycle.changes_applied > 0 or cycle.patterns_detected > 0,
                "timestamp": cycle.completed_at.isoformat() if cycle.completed_at else self._time_service.now().isoformat()
            }
        )

        if self._memory_bus:
            await self._memory_bus.memorize(
                node=summary_node,
                handler_name="self_configuration",
                metadata={"cycle_summary": True}
            )

    async def get_adaptation_status(self) -> AdaptationStatus:
        """Get current status of the self-configuration system."""
        status = AdaptationStatus(
            is_active=not self._emergency_stop,
            current_state=self._current_state,
            cycles_completed=len(self._adaptation_history),
            last_cycle_at=self._last_adaptation,
            current_variance=self._variance_monitor.current_variance if self._variance_monitor else 0.0,
            patterns_in_buffer=0,  # No more proposal buffer
            pending_proposals=0,  # No more proposals
            average_cycle_duration_seconds=0.0,  # TODO: Calculate from history
            total_changes_applied=sum(c.changes_applied for c in self._adaptation_history),
            rollback_rate=0.0,  # TODO: Track rollbacks
            identity_stable=self._consecutive_failures < 3,
            time_since_last_change=(self._time_service.now() - self._last_adaptation).total_seconds() if self._last_adaptation else None,
            under_review=self._current_state == AdaptationState.REVIEWING,
            review_reason="Variance exceeded threshold" if self._current_state == AdaptationState.REVIEWING else None
        )

        return status

    async def resume_after_review(self, review_outcome: ReviewOutcome) -> None:
        """Resume self-configuration after WA review."""
        if self._current_state != AdaptationState.REVIEWING:
            logger.warning("Resume called but not in REVIEWING state")
            return

        # Process review outcome
        if review_outcome.decision == "approve":
            self._current_state = AdaptationState.STABILIZING
            logger.info("WA review approved - entering stabilization")
        else:
            self._current_state = AdaptationState.LEARNING
            logger.info("WA review rejected - returning to learning")

        # Reset failure counter on successful review
        self._consecutive_failures = 0

        # Store review outcome
        review_node = GraphNode(
            id=f"wa_review_outcome_{int(self._time_service.now().timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "review_type": "identity_variance",
                "outcome": review_outcome.model_dump(),
                "new_state": self._current_state.value,
                "timestamp": self._time_service.now().isoformat()
            }
        )

        if self._memory_bus:
            await self._memory_bus.memorize(review_node, handler_name="self_configuration")

    async def emergency_stop(self, reason: str) -> None:
        """Activate emergency stop for self-configuration."""
        self._emergency_stop = True
        logger.error(f"Emergency stop activated: {reason}")

        # Store emergency stop event
        stop_node = GraphNode(
            id=f"emergency_stop_{int(self._time_service.now().timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "event_type": "emergency_stop",
                "reason": reason,
                "previous_state": self._current_state.value,
                "timestamp": self._time_service.now().isoformat()
            }
        )

        if self._memory_bus:
            await self._memory_bus.memorize(stop_node, handler_name="self_configuration")

    async def start(self) -> None:
        """Start the self-configuration service."""
        # Start component services
        if self._variance_monitor:
            await self._variance_monitor.start()
        if self._feedback_loop:
            await self._feedback_loop.start()
        if self._telemetry_service:
            await self._telemetry_service.start()

        logger.info("SelfConfigurationService started - enabling autonomous adaptation within ethical bounds")

    async def stop(self) -> None:
        """Stop the service."""
        # Complete current cycle if any
        if self._current_cycle and not self._current_cycle.completed_at:
            self._current_cycle.completed_at = self._time_service.now()
            await self._store_cycle_summary(self._current_cycle)

        # Stop component services
        if self._variance_monitor:
            await self._variance_monitor.stop()
        if self._feedback_loop:
            await self._feedback_loop.stop()
        if self._telemetry_service:
            await self._telemetry_service.stop()

        logger.info("SelfConfigurationService stopped")

    async def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        if self._emergency_stop:
            return False

        # Check component health
        components_healthy = all([
            await self._variance_monitor.is_healthy() if self._variance_monitor else False,
            await self._feedback_loop.is_healthy() if self._feedback_loop else False,
            await self._telemetry_service.is_healthy() if self._telemetry_service else False
        ])

        return components_healthy and self._consecutive_failures < self._max_failures

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="SelfConfigurationService",
            actions=["adapt_configuration", "monitor_identity", "process_feedback", "emergency_stop"],
            version="1.0.0",
            dependencies=["variance_monitor", "feedback_loop", "telemetry_service"],
            metadata={
                "description": "Autonomous self-configuration and adaptation service",
                "features": [
                    "autonomous_adaptation", "identity_variance_monitoring", "pattern_detection",
                    "configuration_feedback", "safe_adaptation", "wa_review_integration",
                    "emergency_stop", "adaptation_history", "experience_processing"
                ],
                "safety_features": ["emergency_stop", "wa_review", "change_limits"]
            }
        )

    def get_status(self) -> ServiceStatus:
        """Get current service status."""
        return ServiceStatus(
            service_name="SelfConfigurationService",
            service_type="SPECIAL",
            is_healthy=not self._emergency_stop and self._consecutive_failures < self._max_failures,
            uptime_seconds=0.0,  # Would need to track start time
            last_error=None,
            metrics={
                "adaptation_count": float(len(self._adaptation_history)),
                "consecutive_failures": float(self._consecutive_failures),
                "emergency_stop": float(self._emergency_stop),
                "changes_since_last_adaptation": float(sum(c.changes_applied for c in self._adaptation_history[-1:]) if self._adaptation_history else 0)
            },
            last_health_check=self._time_service.now()
        )

    # ========== New Protocol Methods for 1000-Year Operation ==========

    async def initialize_baseline(self, identity: AgentIdentityRoot) -> str:
        """
        Establish identity baseline for variance monitoring.
        This is an alias for _initialize_identity_baseline to match the protocol.
        """
        return await self._initialize_identity_baseline(identity)

    async def analyze_observability_window(
        self,
        window: timedelta = timedelta(hours=6)
    ) -> ObservabilityAnalysis:
        """
        Analyze all observability signals for adaptation opportunities.

        This method looks at insights stored by the feedback loop.
        """
        current_time = self._time_service.now()
        window_start = current_time - window

        analysis = ObservabilityAnalysis(
            window_start=window_start,
            window_end=current_time,
            total_signals=0,
            signals_by_type={},
            opportunities=[]
        )

        if not self._memory_bus:
            return analysis

        # Query for insights in the window
        from ciris_engine.schemas.services.operations import MemoryQuery

        query = MemoryQuery(
            node_id="behavioral_patterns",  # MemoryQuery requires node_id
            scope=GraphScope.LOCAL,
            type=NodeType.CONCEPT,
            include_edges=False,
            depth=1
        )

        insights = await self._memory_bus.recall(query, handler_name="self_configuration")

        # Process insights into opportunities
        for insight in insights:
            if insight.attributes.get("actionable", False):
                opportunity = AdaptationOpportunity(
                    opportunity_id=f"opp_{insight.id}",
                    signal_type=insight.attributes.get("pattern_type", "unknown"),
                    description=insight.attributes.get("description", ""),
                    expected_benefit="Agent can decide to optimize based on this pattern",
                    risk_level="low"  # All insights are pre-filtered as safe
                )
                analysis.opportunities.append(opportunity)

        analysis.total_signals = len(insights)

        return analysis

    async def trigger_adaptation_cycle(self) -> AdaptationCycleResult:
        """
        Manually trigger an adaptation assessment cycle.

        This now just runs a variance check.
        """
        if self._emergency_stop:
            return AdaptationCycleResult(
                cycle_id="manual_trigger_blocked",
                state=self._current_state,
                started_at=self._time_service.now(),
                completed_at=self._time_service.now(),
                success=False,
                error="Emergency stop active"
            )

        # Run variance check
        return await self._run_adaptation_cycle()

    async def get_pattern_library(self) -> PatternLibrarySummary:
        """
        Get summary of learned adaptation patterns.

        Patterns are now insights stored by the feedback loop.
        """
        summary = PatternLibrarySummary(
            total_patterns=0,
            patterns_by_type={},
            most_successful_patterns=[],
            recently_discovered=[]
        )

        if not self._memory_bus:
            return summary

        # Query for pattern nodes
        from ciris_engine.schemas.services.operations import MemoryQuery

        query = MemoryQuery(
            node_id="pattern_library",  # MemoryQuery requires node_id
            scope=GraphScope.LOCAL,
            type=NodeType.CONCEPT,
            include_edges=False,
            depth=1
        )

        patterns = await self._memory_bus.recall(query, handler_name="self_configuration")

        summary.total_patterns = len(patterns)

        # Group by type
        for pattern in patterns:
            pattern_type = pattern.attributes.get("pattern_type", "unknown")
            if pattern_type not in summary.patterns_by_type:
                summary.patterns_by_type[pattern_type] = 0
            summary.patterns_by_type[pattern_type] += 1

        return summary

    async def measure_adaptation_effectiveness(
        self,
        adaptation_id: str
    ) -> AdaptationEffectiveness:
        """
        Measure if an adaptation actually improved the system.

        Since adaptations are now agent-driven, effectiveness
        is measured by variance stability.
        """
        effectiveness = AdaptationEffectiveness(
            adaptation_id=adaptation_id,
            measured_at=self._time_service.now(),
            metrics_before={},
            metrics_after={},
            net_improvement=0.0,
            recommendation="keep"  # Default recommendation
        )

        # Check if variance is stable
        if self._variance_monitor:
            current_variance = self._variance_monitor.current_variance
            if current_variance < self._variance_threshold:
                effectiveness.recommendation = "keep"
                effectiveness.net_improvement = 1.0 - (current_variance / self._variance_threshold)
            else:
                effectiveness.recommendation = "review"

        return effectiveness

    async def get_improvement_report(
        self,
        period: timedelta = timedelta(days=30)
    ) -> ServiceImprovementReport:
        """
        Generate service improvement report for period.
        """
        current_time = self._time_service.now()
        period_start = current_time - period

        report = ServiceImprovementReport(
            report_period_start=period_start,
            report_period_end=current_time,
            total_adaptations=0,
            successful_adaptations=0,
            rolled_back_adaptations=0,
            average_improvement_per_adaptation=0.0,
            most_impactful_changes=[],
            stability_score=1.0 if self._consecutive_failures == 0 else 0.5,
            recommendations=[]
        )

        # Count variance checks in period
        for cycle in self._adaptation_history:
            if hasattr(cycle, 'started_at') and cycle.started_at >= period_start:
                report.total_adaptations += 1
                if hasattr(cycle, 'success') and cycle.success:
                    report.successful_adaptations += 1

        # Add recommendations based on current state
        if self._emergency_stop:
            report.recommendations.append("Clear emergency stop and investigate cause")
        if self._consecutive_failures > 0:
            report.recommendations.append("Investigate variance check failures")

        return report
