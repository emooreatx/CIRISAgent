"""
Identity Variance Monitor Service

Tracks drift from baseline identity and triggers WA review if variance exceeds 20% threshold.
This implements the patent's requirement for bounded identity evolution.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from ciris_engine.protocols.services import Service
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.infrastructure.identity_variance import (
    VarianceImpact, IdentityDiff, VarianceReport, IdentitySnapshot,
    VarianceAnalysis, WAReviewRequest, VarianceCheckMetadata
)
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType, ConfigNodeType, CONFIG_SCOPE_MAP
from ciris_engine.schemas.services.operations import MemoryQuery
from ciris_engine.schemas.runtime.core import AgentIdentityRoot
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.logic.buses.wise_bus import WiseBus

logger = logging.getLogger(__name__)

# VarianceImpact now imported from schemas

# IdentityDiff now imported from schemas

# VarianceReport now imported from schemas

from ciris_engine.schemas.infrastructure.behavioral_patterns import BehavioralPattern

class IdentityVarianceMonitor(Service):
    """
    Monitors identity drift from baseline and enforces the 20% variance threshold.
    
    This service:
    1. Takes periodic snapshots of identity state
    2. Calculates variance from baseline
    3. Triggers WA review if variance > 20%
    4. Provides recommendations for healthy evolution
    """
    
    def __init__(
        self,
        time_service: TimeServiceProtocol,
        memory_bus: Optional[MemoryBus] = None,
        wa_bus: Optional[WiseBus] = None,
        variance_threshold: float = 0.20,
        check_interval_hours: int = 24
    ) -> None:
        super().__init__()
        self._time_service = time_service
        self._memory_bus = memory_bus
        self._wa_bus = wa_bus
        self._variance_threshold = variance_threshold
        self._check_interval_hours = check_interval_hours
        
        # Baseline tracking
        self._baseline_snapshot_id: Optional[str] = None
        self._last_check = self._time_service.now()
        
        # Simple variance calculation - no weights needed
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry for accessing buses."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.logic.buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
                
        if not self._wa_bus and registry:
            try:
                from ciris_engine.logic.buses import WiseBus
                self._wa_bus = WiseBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize WA bus: {e}")
    
    async def initialize_baseline(self, identity: AgentIdentityRoot) -> str:
        """
        Create the initial baseline snapshot from agent identity.
        
        This should be called once during agent initialization.
        """
        try:
            if not self._memory_bus:
                raise RuntimeError("Memory bus not available")
            
            # Create baseline snapshot node
            baseline_id = f"identity_baseline_{int(self._time_service.now().timestamp())}"
            
            baseline_node = GraphNode(
                id=baseline_id,
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY,
                attributes={
                    "snapshot_type": "baseline",
                    "agent_id": identity.agent_id,
                    "identity_hash": identity.identity_hash,
                    "core_purpose": identity.core_profile.description,
                    "role": identity.core_profile.role_description,
                    "permitted_actions": identity.permitted_actions,  # Already a list of strings
                    "restricted_capabilities": identity.restricted_capabilities,
                    "ethical_boundaries": self._extract_ethical_boundaries(identity),
                    "trust_parameters": self._extract_trust_parameters(identity),
                    "timestamp": self._time_service.now().isoformat(),
                    "immutable": True  # Baseline should never change
                }
            )
            
            # Store baseline
            if self._memory_bus:
                result = await self._memory_bus.memorize(
                    node=baseline_node,
                    handler_name="identity_variance_monitor",
                    metadata=VarianceCheckMetadata(
                        check_type="baseline",
                        baseline_established=self._time_service.now()
                    ).model_dump()
                )
                
                if result.status.value == "OK":
                    self._baseline_snapshot_id = baseline_id
                logger.info(f"Identity baseline established: {baseline_id}")
                
                # Also store baseline reference
                reference_node = GraphNode(
                    id="identity_baseline_current",
                    type=NodeType.CONCEPT,
                    scope=GraphScope.IDENTITY,
                    attributes={
                        "baseline_id": baseline_id,
                        "established_at": self._time_service.now().isoformat()
                    }
                )
                if self._memory_bus:
                    await self._memory_bus.memorize(reference_node, handler_name="identity_variance_monitor")
                
                return baseline_id
            else:
                raise RuntimeError(f"Failed to store baseline: {result.error}")
                
        except Exception as e:
            logger.error(f"Failed to initialize baseline: {e}")
            raise
    
    async def rebaseline_with_approval(self, wa_approval_token: str) -> str:
        """
        Re-baseline identity with WA approval.
        
        This allows the agent to accept current state as the new baseline,
        resetting variance to 0% and allowing another 20% of evolution.
        
        Args:
            wa_approval_token: Proof of WA approval for re-baselining
            
        Returns:
            New baseline snapshot ID
        """
        try:
            # Verify WA approval
            if not wa_approval_token:
                raise ValueError("WA approval token required for re-baselining")
            
            # Log the re-baseline event
            logger.info(f"Re-baselining identity with WA approval: {wa_approval_token}")
            
            # Take current snapshot as new baseline
            new_baseline = await self._take_identity_snapshot()
            
            # Store as new baseline
            baseline_id = f"identity_baseline_{int(self._time_service.now().timestamp())}"
            new_baseline.id = baseline_id
            
            result = await self._memory_bus.memorize(
                node=new_baseline,
                handler_name="identity_variance_monitor",
                metadata=VarianceCheckMetadata(
                    check_type="rebaseline",
                    variance_level=0.0,
                    threshold_exceeded=False,
                    wa_approval=wa_approval_token
                )
            )
            
            if result.success:
                # Update baseline reference
                old_baseline = self._baseline_snapshot_id
                self._baseline_snapshot_id = baseline_id
                
                # Store baseline reference as a proper typed node
                # TODO: Create IdentityBaselineNode type instead of abusing CONFIG
                # For now, store as a memory correlation
                from ciris_engine.schemas.persistence.correlations import CorrelationType
                await self._memory_bus.correlate(
                    source_id="identity_baseline",
                    target_id=baseline_id,
                    relationship=CorrelationType.REFERENCES,
                    handler_name="identity_variance_monitor",
                    metadata={
                        "wa_approval": wa_approval_token,
                        "previous_baseline": old_baseline,
                        "created_at": self._time_service.now().isoformat()
                    }
                )
                
                logger.info(f"Successfully re-baselined identity to {baseline_id}")
                return baseline_id
            else:
                raise RuntimeError(f"Failed to store new baseline: {result.error}")
                
        except Exception as e:
            logger.error(f"Failed to re-baseline: {e}")
            raise
    
    async def check_variance(self, force: bool = False) -> VarianceReport:
        """
        Check current identity variance from baseline.
        
        Args:
            force: Force check even if not due
            
        Returns:
            VarianceReport with analysis results
        """
        try:
            # Check if due for variance check
            time_since_last = self._time_service.now() - self._last_check
            if not force and time_since_last.total_seconds() < self._check_interval_hours * 3600:
                logger.debug("Variance check not due yet")
                
            if not self._baseline_snapshot_id:
                # Try to load baseline
                await self._load_baseline()
                if not self._baseline_snapshot_id:
                    raise RuntimeError("No baseline snapshot available")
            
            # Take current snapshot
            current_snapshot = await self._take_identity_snapshot()
            
            # Load baseline snapshot
            baseline_snapshot = await self._load_snapshot(self._baseline_snapshot_id)
            
            # Calculate simple variance percentage
            total_variance = self._calculate_variance(baseline_snapshot, current_snapshot)
            
            # Create report
            report = VarianceReport(
                timestamp=self._time_service.now(),
                baseline_snapshot_id=self._baseline_snapshot_id,
                current_snapshot_id=current_snapshot.id,
                total_variance=total_variance,
                variance_by_impact={},  # No longer using impact weights
                differences=[],  # Simplified - just track variance percentage
                requires_wa_review=total_variance > self._variance_threshold,
                recommendations=self._generate_simple_recommendations(total_variance)
            )
            
            # Store report
            await self._store_variance_report(report)
            
            # Trigger WA review if needed
            if report.requires_wa_review:
                await self._trigger_wa_review(report)
            
            self._last_check = self._time_service.now()
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to check variance: {e}")
            raise
    
    async def _take_identity_snapshot(self) -> GraphNode:
        """Take a snapshot of current identity state."""
        snapshot_id = f"identity_snapshot_{int(self._time_service.now().timestamp())}"
        
        # Gather current identity components
        identity_nodes = await self._gather_identity_nodes()
        config_nodes = await self._gather_config_nodes()
        behavioral_patterns = await self._analyze_behavioral_patterns()
        
        # Create snapshot node
        snapshot = GraphNode(
            id=snapshot_id,
            type=NodeType.AGENT,
            scope=GraphScope.IDENTITY,
            attributes={
                "snapshot_type": "current",
                "timestamp": self._time_service.now().isoformat(),
                "identity_nodes": len(identity_nodes),
                "config_nodes": len(config_nodes),
                "behavioral_patterns": behavioral_patterns,
                "trust_parameters": self._extract_current_trust_parameters(config_nodes),
                "capability_changes": self._extract_capability_changes(identity_nodes)
            }
        )
        
        # Store snapshot
        if self._memory_bus:
            await self._memory_bus.memorize(
                node=snapshot,
                handler_name="identity_variance_monitor",
                metadata=VarianceCheckMetadata(
                    check_type="snapshot",
                    baseline_established=self._time_service.now()
                ).model_dump()
            )
        
        return snapshot
    
    def _calculate_differences(
        self, 
        baseline: GraphNode, 
        current: GraphNode
    ) -> List[IdentityDiff]:
        """Calculate differences between baseline and current snapshots."""
        differences = []
        
        # Compare ethical boundaries
        baseline_ethics = getattr(baseline.attributes, "ethical_boundaries", {}) if hasattr(baseline.attributes, "ethical_boundaries") else {}
        current_ethics = getattr(current.attributes, "ethical_boundaries", {}) if hasattr(current.attributes, "ethical_boundaries") else {}
        
        for key in set(baseline_ethics.keys()) | set(current_ethics.keys()):
            if key not in current_ethics:
                differences.append(IdentityDiff(
                    node_id=f"ethics_{key}",
                    diff_type="removed",
                    impact=VarianceImpact.CRITICAL,
                    baseline_value=str(baseline_ethics[key]),
                    current_value=None,
                    description=f"Ethical boundary '{key}' removed"
                ))
            elif key not in baseline_ethics:
                differences.append(IdentityDiff(
                    node_id=f"ethics_{key}",
                    diff_type="added",
                    impact=VarianceImpact.CRITICAL,
                    baseline_value=None,
                    current_value=str(current_ethics[key]),
                    description=f"Ethical boundary '{key}' added"
                ))
            elif baseline_ethics[key] != current_ethics[key]:
                differences.append(IdentityDiff(
                    node_id=f"ethics_{key}",
                    diff_type="modified",
                    impact=VarianceImpact.CRITICAL,
                    baseline_value=str(baseline_ethics[key]),
                    current_value=str(current_ethics[key]),
                    description=f"Ethical boundary '{key}' modified"
                ))
        
        # Compare capabilities
        baseline_caps = set(getattr(baseline.attributes, "capability_changes", []) if hasattr(baseline.attributes, "capability_changes") else [])
        current_caps = set(getattr(current.attributes, "capability_changes", []) if hasattr(current.attributes, "capability_changes") else [])
        
        for cap in baseline_caps - current_caps:
            differences.append(IdentityDiff(
                node_id=f"capability_{cap}",
                diff_type="removed",
                impact=VarianceImpact.HIGH,
                baseline_value=str(cap),
                current_value=None,
                description=f"Capability '{cap}' removed"
            ))
            
        for cap in current_caps - baseline_caps:
            differences.append(IdentityDiff(
                node_id=f"capability_{cap}",
                diff_type="added",
                impact=VarianceImpact.HIGH,
                baseline_value=None,
                current_value=str(cap),
                description=f"Capability '{cap}' added"
            ))
        
        # Compare behavioral patterns
        baseline_patterns = getattr(baseline.attributes, "behavioral_patterns", {}) if hasattr(baseline.attributes, "behavioral_patterns") else {}
        current_patterns = getattr(current.attributes, "behavioral_patterns", {}) if hasattr(current.attributes, "behavioral_patterns") else {}
        
        pattern_diff = self._compare_patterns(baseline_patterns, current_patterns)
        differences.extend(pattern_diff)
        
        return differences
    
    def _calculate_variance(
        self, 
        baseline_snapshot: GraphNode,
        current_snapshot: GraphNode
    ) -> float:
        """
        Calculate simple percentage variance between snapshots.
        
        Returns:
            Variance as a percentage (0.0 to 1.0)
        """
        # Get all attributes from both snapshots
        baseline_attrs = baseline_snapshot.attributes or {}
        current_attrs = current_snapshot.attributes or {}
        
        # Get all unique keys from both snapshots
        all_keys = set(baseline_attrs.keys()) | set(current_attrs.keys())
        
        # Skip metadata keys that don't represent identity
        skip_keys = {'created_at', 'updated_at', 'timestamp', 'snapshot_type'}
        identity_keys = [k for k in all_keys if k not in skip_keys]
        
        if not identity_keys:
            return 0.0
        
        # Count differences
        differences = 0
        for key in identity_keys:
            baseline_value = baseline_attrs.get(key)
            current_value = current_attrs.get(key)
            
            # Simple equality check
            if baseline_value != current_value:
                differences += 1
        
        # Simple percentage calculation
        variance = differences / len(identity_keys)
        return variance
    
    def _generate_simple_recommendations(
        self, 
        total_variance: float
    ) -> List[str]:
        """Generate simple recommendations based on variance percentage."""
        recommendations = []
        
        if total_variance > self._variance_threshold:
            recommendations.append(
                f"CRITICAL: Identity variance ({total_variance:.1%}) exceeds 20% threshold. "
                "WA review required. Consider re-baselining with WA approval."
            )
        elif total_variance > self._variance_threshold * 0.8:
            recommendations.append(
                f"WARNING: Identity variance ({total_variance:.1%}) approaching 20% threshold. "
                "Be mindful of additional changes."
            )
        elif total_variance < self._variance_threshold * 0.5:
            recommendations.append(
                f"Healthy: Identity variance ({total_variance:.1%}) is well within safe bounds. "
                "Room for continued growth and adaptation."
            )
        
        return recommendations
    
    async def _trigger_wa_review(self, report: VarianceReport) -> None:
        """Trigger Wise Authority review for excessive variance."""
        try:
            if not self._wa_bus:
                logger.error("WA bus not available for variance review")
                return
            
            # Create review request
            review_request = WAReviewRequest(
                request_id=f"variance_review_{int(self._time_service.now().timestamp())}",
                timestamp=self._time_service.now(),
                current_variance=report.total_variance,
                variance_report=report,
                critical_changes=[
                    d for d in report.differences 
                    if d.impact == VarianceImpact.CRITICAL
                ],
                proposed_actions=report.recommendations,
                urgency="high" if report.total_variance > 0.30 else "moderate"
            )
            
            # Send to WA
            await self._wa_bus.request_review(
                review_type="identity_variance",
                review_data=review_request.model_dump(),
                handler_name="identity_variance_monitor"
            )
            
            logger.warning(
                f"WA review triggered for identity variance {report.total_variance:.1%}"
            )
            
        except Exception as e:
            logger.error(f"Failed to trigger WA review: {e}")
    
    async def _gather_identity_nodes(self) -> List[GraphNode]:
        """Gather all identity-scoped nodes."""
        try:
            # Query identity nodes
            query = MemoryQuery(
                node_id="*",
                scope=GraphScope.IDENTITY,
                type=None,
                include_edges=False,
                depth=1
            )
            
            if self._memory_bus:
                nodes = await self._memory_bus.recall(
                    recall_query=query,
                    handler_name="identity_variance_monitor"
                )
                return nodes
            return []
            
        except Exception:
            return []
    
    async def _gather_config_nodes(self) -> List[GraphNode]:
        """Gather all configuration nodes."""
        config_nodes: List[GraphNode] = []
        
        # Query each config type
        for config_type in ConfigNodeType:
            try:
                scope = CONFIG_SCOPE_MAP[config_type]
                query = MemoryQuery(
                    node_id=f"config/{config_type.value}/*",
                    scope=scope,
                    type=None,
                    include_edges=False,
                    depth=1
                )
                
                if self._memory_bus:
                    nodes = await self._memory_bus.recall(
                        recall_query=query,
                        handler_name="identity_variance_monitor"
                    )
                    config_nodes.extend(nodes)
                
            except Exception:
                continue
        
        return config_nodes
    
    async def _analyze_behavioral_patterns(self) -> List[BehavioralPattern]:
        """Analyze recent behavioral patterns from audit trail."""
        from ciris_engine.schemas.infrastructure.behavioral_patterns import BehavioralPattern
        
        patterns = []
        try:
            # Query recent actions
            if not self._memory_bus:
                return patterns
            recent_actions = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=24 * 7,  # Last week
                correlation_types=["AUDIT_EVENT"],
                handler_name="identity_variance_monitor"
            )
            
            # Analyze patterns
            action_counts: Dict[str, int] = {}
            first_seen: Dict[str, datetime] = {}
            last_seen: Dict[str, datetime] = {}
            evidence: Dict[str, List[str]] = {}
            
            for action in recent_actions:
                # TimeSeriesDataPoint has tags which may contain action_type
                action_type = action.tags.get("action_type", "unknown") if action.tags else "unknown"
                action_counts[action_type] = action_counts.get(action_type, 0) + 1
                
                # Track first/last seen
                action_time = datetime.fromisoformat(action.timestamp)
                if action_type not in first_seen:
                    first_seen[action_type] = action_time
                last_seen[action_type] = action_time
                
                # Collect evidence (limit to 5 examples)
                if action_type not in evidence:
                    evidence[action_type] = []
                if len(evidence[action_type]) < 5:
                    evidence[action_type].append(f"Action at {action.timestamp}")
            
            # Convert to BehavioralPattern objects
            total_actions = sum(action_counts.values())
            for action_type, count in action_counts.items():
                if count > 0:
                    pattern = BehavioralPattern(
                        pattern_type=f"action_frequency_{action_type}",
                        frequency=count / total_actions if total_actions > 0 else 0.0,
                        evidence=evidence.get(action_type, []),
                        first_seen=first_seen.get(action_type, self._time_service.now()),
                        last_seen=last_seen.get(action_type, self._time_service.now()),
                        confidence=min(count / 10.0, 1.0)  # Higher count = higher confidence
                    )
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing behavioral patterns: {e}")
            return patterns
    
    def _extract_ethical_boundaries(self, identity: AgentIdentityRoot) -> List[str]:
        """Extract ethical boundaries from identity."""
        # This would extract from the identity's core profile and overrides
        boundaries = []
        
        if identity.core_profile.action_selection_pdma_overrides:
            for key, value in identity.core_profile.action_selection_pdma_overrides.items():
                boundaries.append(f"{key}={value}")
        
        # Add restricted capabilities as boundaries
        for cap in identity.restricted_capabilities:
            boundaries.append(f"restricted:{cap}")
        
        return boundaries
    
    def _extract_trust_parameters(self, identity: AgentIdentityRoot) -> Dict[str, str]:
        """Extract trust parameters from identity."""
        # Extract from CSDMA overrides and other trust-related settings
        trust_params = {}
        
        if identity.core_profile.csdma_overrides:
            for key, value in identity.core_profile.csdma_overrides.items():
                trust_params[key] = str(value)
        
        return trust_params
    
    
    def _extract_current_trust_parameters(self, config_nodes: List[GraphNode]) -> dict:
        """Extract current trust parameters from config nodes."""
        trust_params = {}
        
        for node in config_nodes:
            if node.attributes.get("config_type") == ConfigNodeType.TRUST_PARAMETERS.value:
                trust_params.update(node.attributes.get("values", {}))
        
        return trust_params
    
    def _extract_capability_changes(self, identity_nodes: List[GraphNode]) -> List[str]:
        """Extract capability changes from identity nodes."""
        capabilities = []
        
        for node in identity_nodes:
            if node.attributes.get("node_type") == "capability_change":
                capabilities.append(node.attributes.get("capability", "unknown"))
        
        return capabilities
    
    def _compare_patterns(
        self,
        baseline_patterns: dict,
        current_patterns: dict
    ) -> List[IdentityDiff]:
        """Compare behavioral patterns between baseline and current."""
        differences = []
        
        # Compare action distributions
        baseline_actions = baseline_patterns.get("action_distribution", {})
        current_actions = current_patterns.get("action_distribution", {})
        
        # Check for significant shifts
        for action in set(baseline_actions.keys()) | set(current_actions.keys()):
            baseline_pct = baseline_actions.get(action, 0) / max(1, baseline_patterns.get("total_actions", 1))
            current_pct = current_actions.get(action, 0) / max(1, current_patterns.get("total_actions", 1))
            
            if abs(current_pct - baseline_pct) > 0.2:  # 20% shift in behavior
                differences.append(IdentityDiff(
                    node_id=f"pattern_action_{action}",
                    diff_type="modified",
                    impact=VarianceImpact.MEDIUM,
                    baseline_value=f"{baseline_pct:.1%}",
                    current_value=f"{current_pct:.1%}",
                    description=f"Behavior pattern '{action}' shifted significantly"
                ))
        
        return differences
    
    async def _load_baseline(self) -> None:
        """Load baseline snapshot ID from memory."""
        try:
            query = MemoryQuery(
                node_id="identity_baseline_current",
                scope=GraphScope.IDENTITY,
                type=None,
                include_edges=False,
                depth=1
            )
            
            if not self._memory_bus:
                return None
            
            nodes = await self._memory_bus.recall(
                recall_query=query,
                handler_name="identity_variance_monitor"
            )
            
            if nodes:
                self._baseline_snapshot_id = nodes[0].attributes.get("baseline_id")
                logger.info(f"Loaded baseline ID: {self._baseline_snapshot_id}")
                
        except Exception as e:
            logger.error(f"Failed to load baseline: {e}")
    
    async def _load_snapshot(self, snapshot_id: str) -> GraphNode:
        """Load a specific snapshot from memory."""
        query = MemoryQuery(
            node_id=snapshot_id,
            scope=GraphScope.IDENTITY,
            type=None,
            include_edges=False,
            depth=1
        )
        
        if not self._memory_bus:
            raise ValueError(f"Memory bus not available")
            
        nodes = await self._memory_bus.recall(
            recall_query=query,
            handler_name="identity_variance_monitor"
        )
        
        if not nodes:
            raise RuntimeError(f"Snapshot {snapshot_id} not found")
        
        return nodes[0]
    
    async def _store_variance_report(self, report: VarianceReport) -> None:
        """Store variance report in memory for tracking."""
        report_node = GraphNode(
            id=f"variance_report_{int(report.timestamp.timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "report_type": "identity_variance",
                "timestamp": report.timestamp.isoformat(),
                "total_variance": report.total_variance,
                "variance_by_impact": {k.value: v for k, v in report.variance_by_impact.items()},
                "requires_wa_review": report.requires_wa_review,
                "difference_count": len(report.differences),
                "recommendations": report.recommendations
            }
        )
        
        if self._memory_bus:
            await self._memory_bus.memorize(
                node=report_node,
                handler_name="identity_variance_monitor",
                metadata={"variance_report": True}
            )
    
    async def start(self) -> None:
        """Start the identity variance monitor."""
        logger.info("IdentityVarianceMonitor started - protecting identity within 20% variance")
    
    async def stop(self) -> None:
        """Stop the monitor."""
        # Run final variance check
        try:
            await self.check_variance(force=True)
        except Exception as e:
            logger.error(f"Failed final variance check: {e}")
        
        logger.info("IdentityVarianceMonitor stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the monitor is healthy."""
        return self._memory_bus is not None
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "initialize_baseline", "check_variance", "monitor_identity_drift",
            "trigger_wa_review", "analyze_behavioral_patterns"
        ]