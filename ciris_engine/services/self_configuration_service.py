"""
Self-Configuration Service

Orchestrates all self-configuration components to enable autonomous adaptation
within safe ethical boundaries. This is the master coordinator that ties together:
- IdentityVarianceMonitor (tracks drift from baseline)
- ConfigurationFeedbackLoop (detects patterns and proposes changes)
- UnifiedTelemetryService (provides the data flow)

Together, these enable the agent to learn and adapt while maintaining its core identity.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

from ciris_engine.protocols.services import Service
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType, AdaptationProposalNode
from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
from ciris_engine.services.identity_variance_monitor import IdentityVarianceMonitor
from ciris_engine.services.configuration_feedback_loop import ConfigurationFeedbackLoop
from ciris_engine.services.unified_telemetry_service import UnifiedTelemetryService
from ciris_engine.message_buses.memory_bus import MemoryBus

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


class SelfConfigurationService(Service):
    """
    Master service that orchestrates self-configuration and autonomous adaptation.
    
    This service:
    1. Coordinates between variance monitoring, pattern detection, and telemetry
    2. Manages the adaptation lifecycle with safety checks
    3. Ensures changes stay within the 20% identity variance threshold
    4. Provides a unified interface for self-configuration
    
    The flow:
    Experience → Telemetry → Patterns → Proposals → Variance Check → Adaptation → New Behavior
    """
    
    def __init__(
        self,
        memory_bus: Optional[MemoryBus] = None,
        variance_threshold: float = 0.20,
        adaptation_interval_hours: int = 6,
        stabilization_period_hours: int = 24
    ) -> None:
        super().__init__()
        self._memory_bus = memory_bus
        self._variance_threshold = variance_threshold
        self._adaptation_interval = timedelta(hours=adaptation_interval_hours)
        self._stabilization_period = timedelta(hours=stabilization_period_hours)
        
        # Component services
        self._variance_monitor: Optional[IdentityVarianceMonitor] = None
        self._feedback_loop: Optional[ConfigurationFeedbackLoop] = None
        self._telemetry_service: Optional[UnifiedTelemetryService] = None
        
        # State tracking
        self._current_state = AdaptationState.LEARNING
        self._current_cycle: Optional[AdaptationCycle] = None
        self._adaptation_history: List[AdaptationCycle] = []
        self._last_adaptation = datetime.now(timezone.utc)
        self._pending_proposals: List[AdaptationProposalNode] = []
        
        # Safety mechanisms
        self._emergency_stop = False
        self._consecutive_failures = 0
        self._max_failures = 3
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry and initialize component services."""
        self._service_registry = registry
        
        # Initialize memory bus
        if not self._memory_bus and registry:
            try:
                from ciris_engine.message_buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
        
        # Initialize component services
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize the component services."""
        try:
            # Create variance monitor
            self._variance_monitor = IdentityVarianceMonitor(
                memory_bus=self._memory_bus,
                variance_threshold=self._variance_threshold
            )
            if self._service_registry:
                self._variance_monitor.set_service_registry(self._service_registry)
            
            # Create feedback loop
            self._feedback_loop = ConfigurationFeedbackLoop(
                memory_bus=self._memory_bus,
                analysis_interval_hours=int(self._adaptation_interval.total_seconds() / 3600)
            )
            if self._service_registry:
                self._feedback_loop.set_service_registry(self._service_registry)
            
            # Create telemetry service
            self._telemetry_service = UnifiedTelemetryService(
                memory_bus=self._memory_bus
            )
            if self._service_registry:
                self._telemetry_service.set_service_registry(self._service_registry)
            
            logger.info("Self-configuration components initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
    
    async def initialize_identity_baseline(self, identity: AgentIdentityRoot) -> str:
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
            id=f"self_config_init_{int(datetime.now(timezone.utc).timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "event_type": "self_configuration_initialized",
                "baseline_id": baseline_id,
                "variance_threshold": self._variance_threshold,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        if self._memory_bus:
            await self._memory_bus.memorize(init_node, handler_name="self_configuration")
        
        return baseline_id
    
    async def process_experience(
        self, 
        snapshot: SystemSnapshot,
        thought_id: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an experience snapshot through the self-configuration pipeline.
        
        This is the main entry point for the experience → adaptation flow.
        """
        try:
            if self._emergency_stop:
                return {"status": "emergency_stop", "reason": "Self-configuration halted"}
            
            results: Dict[str, Any] = {
                "snapshot_processed": False,
                "adaptation_triggered": False,
                "current_state": self._current_state.value,
                "errors": []
            }
            
            # 1. Process through unified telemetry (Experience → Memory)
            if self._telemetry_service:
                telemetry_result = await self._telemetry_service.process_system_snapshot(
                    snapshot, thought_id, task_id
                )
                results["snapshot_processed"] = True
                results["memories_created"] = telemetry_result.get("memories_created", 0)
            
            # 2. Check if adaptation cycle is due
            if await self._should_run_adaptation_cycle():
                cycle_result = await self._run_adaptation_cycle()
                results["adaptation_triggered"] = True
                results["adaptation_result"] = cycle_result
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process experience: {e}")
            return {"status": "error", "error": str(e)}
    
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
            time_since_last = datetime.now(timezone.utc) - self._last_adaptation
            if time_since_last < self._stabilization_period:
                return False
        
        # Check interval
        time_since_last = datetime.now(timezone.utc) - self._last_adaptation
        return time_since_last >= self._adaptation_interval
    
    async def _run_adaptation_cycle(self) -> Dict[str, Any]:
        """
        Run a complete adaptation cycle.
        
        Flow:
        1. Check current variance
        2. Detect patterns and generate proposals
        3. Filter proposals by variance impact
        4. Apply safe proposals
        5. Re-check variance
        6. Update state
        """
        try:
            # Start new cycle
            cycle_id = f"cycle_{int(datetime.now(timezone.utc).timestamp())}"
            self._current_cycle = AdaptationCycle(
                cycle_id=cycle_id,
                started_at=datetime.now(timezone.utc),
                state=self._current_state,
                patterns_detected=0,
                proposals_generated=0,
                changes_applied=0,
                variance_before=0.0,
                variance_after=None,
                completed_at=None
            )
            
            logger.info(f"Starting adaptation cycle {cycle_id}")
            
            # 1. Check current variance
            if self._variance_monitor:
                variance_report = await self._variance_monitor.check_variance()
                self._current_cycle.variance_before = variance_report.total_variance
            else:
                variance_report = None
                self._current_cycle.variance_before = 0.0
            
            if variance_report and variance_report.requires_wa_review:
                # Variance too high - enter review state
                self._current_state = AdaptationState.REVIEWING
                self._current_cycle.state = AdaptationState.REVIEWING
                await self._store_cycle_event("variance_exceeded", {
                    "variance": variance_report.total_variance,
                    "threshold": self._variance_threshold
                })
                return {
                    "status": "wa_review_required",
                    "variance": variance_report.total_variance,
                    "cycle_id": cycle_id
                }
            
            # 2. Run pattern detection and proposal generation
            if self._feedback_loop:
                feedback_result = await self._feedback_loop.analyze_and_adapt(force=True)
                self._current_cycle.patterns_detected = feedback_result.get("patterns_detected", 0)
                self._current_cycle.proposals_generated = feedback_result.get("proposals_generated", 0)
                
                # Get pending proposals
                self._pending_proposals = await self._get_pending_proposals()
            
            # 3. Filter proposals by projected variance impact
            safe_proposals = await self._filter_safe_proposals(
                self._pending_proposals,
                variance_report.total_variance if variance_report else 0.0
            )
            
            # 4. Apply safe proposals
            if safe_proposals:
                self._current_state = AdaptationState.ADAPTING
                applied_count = await self._apply_proposals(safe_proposals)
                self._current_cycle.changes_applied = applied_count
                
                # 5. Re-check variance after changes
                if self._variance_monitor:
                    post_variance = await self._variance_monitor.check_variance()
                else:
                    post_variance = None
                if post_variance:
                    self._current_cycle.variance_after = post_variance.total_variance
                else:
                    self._current_cycle.variance_after = 0.0
                
                if post_variance and post_variance.requires_wa_review:
                    # Changes pushed us over threshold
                    self._current_state = AdaptationState.REVIEWING
                    await self._rollback_changes(safe_proposals)
                    logger.warning("Changes exceeded variance threshold - rolled back")
            
            # 6. Complete cycle and update state
            self._current_cycle.completed_at = datetime.now(timezone.utc)
            self._adaptation_history.append(self._current_cycle)
            
            # Determine next state
            if self._current_cycle.changes_applied > 0:
                self._current_state = AdaptationState.STABILIZING
                self._last_adaptation = datetime.now(timezone.utc)
            else:
                self._current_state = AdaptationState.LEARNING
            
            # Store cycle summary
            await self._store_cycle_summary(self._current_cycle)
            
            return {
                "status": "completed",
                "cycle_id": cycle_id,
                "patterns_detected": self._current_cycle.patterns_detected,
                "proposals_generated": self._current_cycle.proposals_generated,
                "changes_applied": self._current_cycle.changes_applied,
                "variance_before": self._current_cycle.variance_before,
                "variance_after": self._current_cycle.variance_after,
                "new_state": self._current_state.value
            }
            
        except Exception as e:
            logger.error(f"Adaptation cycle failed: {e}")
            self._consecutive_failures += 1
            
            if self._consecutive_failures >= self._max_failures:
                self._emergency_stop = True
                logger.error("Emergency stop activated after repeated failures")
            
            return {"status": "failed", "error": str(e)}
    
    async def _filter_safe_proposals(
        self,
        proposals: List[AdaptationProposalNode],
        current_variance: float
    ) -> List[AdaptationProposalNode]:
        """
        Filter proposals to only include those that won't exceed variance threshold.
        
        This is a critical safety mechanism.
        """
        safe_proposals = []
        remaining_variance = self._variance_threshold - current_variance
        
        if remaining_variance <= 0:
            # No room for changes
            return []
        
        # Sort proposals by confidence and scope
        sorted_proposals = sorted(
            proposals,
            key=lambda p: (
                p.scope == GraphScope.LOCAL,  # Prefer LOCAL scope
                p.confidence                   # Then by confidence
            ),
            reverse=True
        )
        
        for proposal in sorted_proposals:
            # Estimate variance impact
            estimated_impact = self._estimate_variance_impact(proposal)
            
            if estimated_impact < remaining_variance * 0.5:  # Conservative: use only half
                safe_proposals.append(proposal)
                remaining_variance -= estimated_impact
            
            if remaining_variance <= 0.05:  # 5% buffer
                break
        
        return safe_proposals
    
    def _estimate_variance_impact(self, proposal: AdaptationProposalNode) -> float:
        """Estimate the variance impact of a proposal."""
        # Base impact by scope
        scope_impacts = {
            GraphScope.LOCAL: 0.02,      # 2% for local changes
            GraphScope.IDENTITY: 0.10,   # 10% for identity changes
            GraphScope.ENVIRONMENT: 0.05, # 5% for environment
            GraphScope.COMMUNITY: 0.03    # 3% for community
        }
        
        base_impact = scope_impacts.get(proposal.scope, 0.05)
        
        # Adjust by number of changes
        change_count = len(proposal.proposed_changes)
        impact_multiplier = 1.0 + (change_count - 1) * 0.2  # 20% more per additional change
        
        return base_impact * impact_multiplier
    
    async def _apply_proposals(self, proposals: List[AdaptationProposalNode]) -> int:
        """Apply the approved proposals."""
        applied = 0
        
        for proposal in proposals:
            try:
                # Record application attempt
                await self._store_cycle_event("applying_proposal", {
                    "proposal_id": proposal.id,
                    "scope": proposal.scope.value,
                    "confidence": proposal.confidence
                })
                
                # Apply through feedback loop
                if self._feedback_loop:
                    result = await self._feedback_loop._apply_configuration_changes(proposal)
                    if result:
                        proposal.applied = True
                        proposal.applied_at = datetime.now(timezone.utc)
                        applied += 1
                        
                        # Update proposal in memory
                        if self._memory_bus:
                            await self._memory_bus.memorize(
                                node=proposal,
                                handler_name="self_configuration",
                                metadata={"applied_by": "self_configuration"}
                            )
                        
            except Exception as e:
                logger.error(f"Failed to apply proposal {proposal.id}: {e}")
        
        return applied
    
    async def _rollback_changes(self, proposals: List[AdaptationProposalNode]) -> None:
        """Rollback changes from proposals (emergency safety)."""
        for proposal in proposals:
            if proposal.applied:
                try:
                    # Create rollback node
                    rollback_node = GraphNode(
                        id=f"rollback_{proposal.id}_{int(datetime.now(timezone.utc).timestamp())}",
                        type=NodeType.CONFIG,
                        scope=proposal.scope,
                        attributes={
                            "rollback_type": "variance_exceeded",
                            "original_proposal": proposal.id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    if self._memory_bus:
                        await self._memory_bus.memorize(
                            node=rollback_node,
                            handler_name="self_configuration"
                        )
                    
                except Exception as e:
                    logger.error(f"Failed to rollback {proposal.id}: {e}")
    
    async def _get_pending_proposals(self) -> List[AdaptationProposalNode]:
        """Get proposals that haven't been applied yet."""
        # Query for unapplied adaptation proposals
        # In a real implementation, this would query the memory graph
        return []
    
    async def _store_cycle_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Store an event during the adaptation cycle."""
        cycle_id = self._current_cycle.cycle_id if self._current_cycle else "unknown"
        event_node = GraphNode(
            id=f"cycle_event_{cycle_id}_{event_type}_{int(datetime.now(timezone.utc).timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={
                "cycle_id": cycle_id,
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
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
                "timestamp": cycle.completed_at.isoformat() if cycle.completed_at else datetime.now(timezone.utc).isoformat()
            }
        )
        
        if self._memory_bus:
            await self._memory_bus.memorize(
                node=summary_node,
                handler_name="self_configuration",
                metadata={"cycle_summary": True}
            )
    
    async def get_adaptation_status(self) -> Dict[str, Any]:
        """Get current status of the self-configuration system."""
        status: Dict[str, Any] = {
            "current_state": self._current_state.value,
            "emergency_stop": self._emergency_stop,
            "consecutive_failures": self._consecutive_failures,
            "cycles_completed": len(self._adaptation_history),
            "last_adaptation": self._last_adaptation.isoformat(),
            "current_cycle": None,
            "recent_history": []
        }
        
        if self._current_cycle:
            status["current_cycle"] = {
                "cycle_id": self._current_cycle.cycle_id,
                "started_at": self._current_cycle.started_at.isoformat(),
                "patterns_detected": self._current_cycle.patterns_detected,
                "proposals_generated": self._current_cycle.proposals_generated,
                "changes_applied": self._current_cycle.changes_applied
            }
        
        # Add recent history
        for cycle in self._adaptation_history[-5:]:  # Last 5 cycles
            status["recent_history"].append({
                "cycle_id": cycle.cycle_id,
                "completed_at": cycle.completed_at.isoformat() if cycle.completed_at else None,
                "changes_applied": cycle.changes_applied,
                "variance_delta": (cycle.variance_after - cycle.variance_before) if cycle.variance_after else 0
            })
        
        return status
    
    async def resume_after_review(self, review_outcome: Dict[str, Any]) -> None:
        """Resume self-configuration after WA review."""
        if self._current_state != AdaptationState.REVIEWING:
            logger.warning("Resume called but not in REVIEWING state")
            return
        
        # Process review outcome
        if review_outcome.get("approved", False):
            self._current_state = AdaptationState.STABILIZING
            logger.info("WA review approved - entering stabilization")
        else:
            self._current_state = AdaptationState.LEARNING
            logger.info("WA review rejected - returning to learning")
        
        # Reset failure counter on successful review
        self._consecutive_failures = 0
        
        # Store review outcome
        review_node = GraphNode(
            id=f"wa_review_outcome_{int(datetime.now(timezone.utc).timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "review_type": "identity_variance",
                "outcome": review_outcome,
                "new_state": self._current_state.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
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
            id=f"emergency_stop_{int(datetime.now(timezone.utc).timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "event_type": "emergency_stop",
                "reason": reason,
                "previous_state": self._current_state.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
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
            self._current_cycle.completed_at = datetime.now(timezone.utc)
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
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "autonomous_adaptation", "identity_variance_monitoring", "pattern_detection",
            "configuration_feedback", "safe_adaptation", "wa_review_integration",
            "emergency_stop", "adaptation_history", "experience_processing"
        ]