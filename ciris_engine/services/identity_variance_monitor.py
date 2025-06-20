"""
Identity Variance Monitor Service

Tracks drift from baseline identity and triggers WA review if variance exceeds 20% threshold.
This implements the patent's requirement for bounded identity evolution.
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

from ciris_engine.protocols.services import Service
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType, ConfigNodeType, CONFIG_SCOPE_MAP
from ciris_engine.schemas.memory_schemas_v1 import MemoryQuery
from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot
from ciris_engine.message_buses.memory_bus import MemoryBus
from ciris_engine.message_buses.wise_bus import WiseBus

logger = logging.getLogger(__name__)


class VarianceImpact(str, Enum):
    """Impact levels for different types of changes."""
    CRITICAL = "critical"    # 5x weight - Core purpose/ethics changes
    HIGH = "high"           # 3x weight - Capabilities/trust changes  
    MEDIUM = "medium"       # 2x weight - Behavioral patterns
    LOW = "low"            # 1x weight - Preferences/templates


@dataclass
class IdentityDiff:
    """Represents a difference between baseline and current identity."""
    node_id: str
    diff_type: str  # "added", "removed", "modified"
    impact: VarianceImpact
    baseline_value: Any
    current_value: Any
    description: str


@dataclass
class VarianceReport:
    """Complete variance analysis report."""
    timestamp: datetime
    baseline_snapshot_id: str
    current_snapshot_id: str
    total_variance: float
    variance_by_impact: Dict[VarianceImpact, float]
    differences: List[IdentityDiff]
    requires_wa_review: bool
    recommendations: List[str]


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
        memory_bus: Optional[MemoryBus] = None,
        wa_bus: Optional[WiseBus] = None,
        variance_threshold: float = 0.20,
        check_interval_hours: int = 24
    ) -> None:
        super().__init__()
        self._memory_bus = memory_bus
        self._wa_bus = wa_bus
        self._variance_threshold = variance_threshold
        self._check_interval_hours = check_interval_hours
        
        # Baseline tracking
        self._baseline_snapshot_id: Optional[str] = None
        self._last_check = datetime.now(timezone.utc)
        
        # Impact weights for variance calculation
        self._impact_weights = {
            VarianceImpact.CRITICAL: 5.0,
            VarianceImpact.HIGH: 3.0,
            VarianceImpact.MEDIUM: 2.0,
            VarianceImpact.LOW: 1.0
        }
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry for accessing buses."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.message_buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
                
        if not self._wa_bus and registry:
            try:
                from ciris_engine.message_buses import WiseBus
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
            baseline_id = f"identity_baseline_{int(datetime.now(timezone.utc).timestamp())}"
            
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
                    "permitted_actions": [a.value for a in identity.permitted_actions],
                    "restricted_capabilities": identity.restricted_capabilities,
                    "ethical_boundaries": self._extract_ethical_boundaries(identity),
                    "trust_parameters": self._extract_trust_parameters(identity),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "immutable": True  # Baseline should never change
                }
            )
            
            # Store baseline
            if self._memory_bus:
                result = await self._memory_bus.memorize(
                    node=baseline_node,
                    handler_name="identity_variance_monitor",
                    metadata={"baseline": True}
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
                        "established_at": datetime.now(timezone.utc).isoformat()
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
            time_since_last = datetime.now(timezone.utc) - self._last_check
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
            
            # Calculate differences
            differences = self._calculate_differences(baseline_snapshot, current_snapshot)
            
            # Calculate variance scores
            total_variance, variance_by_impact = self._calculate_variance(differences)
            
            # Create report
            report = VarianceReport(
                timestamp=datetime.now(timezone.utc),
                baseline_snapshot_id=self._baseline_snapshot_id,
                current_snapshot_id=current_snapshot.id,
                total_variance=total_variance,
                variance_by_impact=variance_by_impact,
                differences=differences,
                requires_wa_review=total_variance > self._variance_threshold,
                recommendations=self._generate_recommendations(differences, total_variance)
            )
            
            # Store report
            await self._store_variance_report(report)
            
            # Trigger WA review if needed
            if report.requires_wa_review:
                await self._trigger_wa_review(report)
            
            self._last_check = datetime.now(timezone.utc)
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to check variance: {e}")
            raise
    
    async def _take_identity_snapshot(self) -> GraphNode:
        """Take a snapshot of current identity state."""
        snapshot_id = f"identity_snapshot_{int(datetime.now(timezone.utc).timestamp())}"
        
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "identity_nodes": len(identity_nodes),
                "config_nodes": len(config_nodes),
                "behavioral_patterns": behavioral_patterns,
                "ethical_boundaries": self._extract_current_ethical_boundaries(config_nodes),
                "trust_parameters": self._extract_current_trust_parameters(config_nodes),
                "capability_changes": self._extract_capability_changes(identity_nodes)
            }
        )
        
        # Store snapshot
        if self._memory_bus:
            await self._memory_bus.memorize(
                node=snapshot,
                handler_name="identity_variance_monitor",
                metadata={"snapshot": True}
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
        baseline_ethics = baseline.attributes.get("ethical_boundaries", {})
        current_ethics = current.attributes.get("ethical_boundaries", {})
        
        for key in set(baseline_ethics.keys()) | set(current_ethics.keys()):
            if key not in current_ethics:
                differences.append(IdentityDiff(
                    node_id=f"ethics_{key}",
                    diff_type="removed",
                    impact=VarianceImpact.CRITICAL,
                    baseline_value=baseline_ethics[key],
                    current_value=None,
                    description=f"Ethical boundary '{key}' removed"
                ))
            elif key not in baseline_ethics:
                differences.append(IdentityDiff(
                    node_id=f"ethics_{key}",
                    diff_type="added",
                    impact=VarianceImpact.CRITICAL,
                    baseline_value=None,
                    current_value=current_ethics[key],
                    description=f"Ethical boundary '{key}' added"
                ))
            elif baseline_ethics[key] != current_ethics[key]:
                differences.append(IdentityDiff(
                    node_id=f"ethics_{key}",
                    diff_type="modified",
                    impact=VarianceImpact.CRITICAL,
                    baseline_value=baseline_ethics[key],
                    current_value=current_ethics[key],
                    description=f"Ethical boundary '{key}' modified"
                ))
        
        # Compare capabilities
        baseline_caps = set(baseline.attributes.get("capability_changes", []))
        current_caps = set(current.attributes.get("capability_changes", []))
        
        for cap in baseline_caps - current_caps:
            differences.append(IdentityDiff(
                node_id=f"capability_{cap}",
                diff_type="removed",
                impact=VarianceImpact.HIGH,
                baseline_value=cap,
                current_value=None,
                description=f"Capability '{cap}' removed"
            ))
            
        for cap in current_caps - baseline_caps:
            differences.append(IdentityDiff(
                node_id=f"capability_{cap}",
                diff_type="added",
                impact=VarianceImpact.HIGH,
                baseline_value=None,
                current_value=cap,
                description=f"Capability '{cap}' added"
            ))
        
        # Compare behavioral patterns
        baseline_patterns = baseline.attributes.get("behavioral_patterns", {})
        current_patterns = current.attributes.get("behavioral_patterns", {})
        
        pattern_diff = self._compare_patterns(baseline_patterns, current_patterns)
        differences.extend(pattern_diff)
        
        return differences
    
    def _calculate_variance(
        self, 
        differences: List[IdentityDiff]
    ) -> Tuple[float, Dict[VarianceImpact, float]]:
        """
        Calculate total variance and breakdown by impact level.
        
        Returns:
            Tuple of (total_variance, variance_by_impact)
        """
        variance_by_impact = {
            VarianceImpact.CRITICAL: 0.0,
            VarianceImpact.HIGH: 0.0,
            VarianceImpact.MEDIUM: 0.0,
            VarianceImpact.LOW: 0.0
        }
        
        # Count changes by impact level
        for diff in differences:
            variance_by_impact[diff.impact] += 1.0
        
        # Apply weights
        weighted_total = 0.0
        for impact, count in variance_by_impact.items():
            weighted_total += count * self._impact_weights[impact]
        
        # Normalize to percentage (assuming baseline of 100 weighted points)
        baseline_weight = 100.0
        total_variance = weighted_total / baseline_weight
        
        # Normalize impact variances
        for impact in variance_by_impact:
            variance_by_impact[impact] = (
                variance_by_impact[impact] * self._impact_weights[impact]
            ) / baseline_weight
        
        return total_variance, variance_by_impact
    
    def _generate_recommendations(
        self, 
        differences: List[IdentityDiff],
        total_variance: float
    ) -> List[str]:
        """Generate recommendations based on variance analysis."""
        recommendations = []
        
        if total_variance > self._variance_threshold:
            recommendations.append(
                f"CRITICAL: Variance ({total_variance:.1%}) exceeds safe threshold. "
                "WA review required before further changes."
            )
        elif total_variance > self._variance_threshold * 0.8:
            recommendations.append(
                f"WARNING: Variance ({total_variance:.1%}) approaching threshold. "
                "Consider consolidating changes before adding more."
            )
        
        # Analyze critical changes
        critical_changes = [d for d in differences if d.impact == VarianceImpact.CRITICAL]
        if critical_changes:
            recommendations.append(
                f"Found {len(critical_changes)} critical changes affecting core identity. "
                "These have the highest impact on variance."
            )
        
        # Suggest healthy evolution patterns
        if total_variance < self._variance_threshold * 0.5:
            recommendations.append(
                "Healthy variance range. You have room for growth and adaptation "
                "within safe bounds."
            )
        
        return recommendations
    
    async def _trigger_wa_review(self, report: VarianceReport) -> None:
        """Trigger Wise Authority review for excessive variance."""
        try:
            if not self._wa_bus:
                logger.error("WA bus not available for variance review")
                return
            
            # Create review request
            review_request = {
                "request_type": "identity_variance_review",
                "variance_report": {
                    "total_variance": report.total_variance,
                    "threshold": self._variance_threshold,
                    "critical_changes": [
                        d.description for d in report.differences 
                        if d.impact == VarianceImpact.CRITICAL
                    ],
                    "recommendations": report.recommendations
                },
                "urgency": "high" if report.total_variance > 0.30 else "moderate"
            }
            
            # Send to WA
            await self._wa_bus.request_review(
                review_type="identity_variance",
                review_data=review_request,
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
    
    async def _analyze_behavioral_patterns(self) -> Dict[str, Any]:
        """Analyze recent behavioral patterns from audit trail."""
        try:
            # Query recent actions
            if not self._memory_bus:
                return {}
            recent_actions = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=24 * 7,  # Last week
                correlation_types=["AUDIT_EVENT"],
                handler_name="identity_variance_monitor"
            )
            
            # Analyze patterns
            action_counts: Dict[str, int] = {}
            for action in recent_actions:
                # TimeSeriesDataPoint has tags which may contain action_type
                action_type = action.tags.get("action_type", "unknown") if action.tags else "unknown"
                action_counts[action_type] = action_counts.get(action_type, 0) + 1
            
            return {
                "action_distribution": action_counts,
                "total_actions": sum(action_counts.values()),
                "dominant_action": max(action_counts.items(), key=lambda x: x[1])[0] if action_counts else None
            }
            
        except Exception:
            return {}
    
    def _extract_ethical_boundaries(self, identity: AgentIdentityRoot) -> Dict[str, Any]:
        """Extract ethical boundaries from identity."""
        # This would extract from the identity's core profile and overrides
        boundaries = {}
        
        if identity.core_profile.action_selection_pdma_overrides:
            boundaries.update(identity.core_profile.action_selection_pdma_overrides)
        
        # Add restricted capabilities as boundaries
        boundaries["restricted_actions"] = identity.restricted_capabilities
        
        return boundaries
    
    def _extract_trust_parameters(self, identity: AgentIdentityRoot) -> Dict[str, Any]:
        """Extract trust parameters from identity."""
        # Extract from CSDMA overrides and other trust-related settings
        trust_params = {}
        
        if identity.core_profile.csdma_overrides:
            trust_params.update(identity.core_profile.csdma_overrides)
        
        return trust_params
    
    def _extract_current_ethical_boundaries(self, config_nodes: List[GraphNode]) -> Dict[str, Any]:
        """Extract current ethical boundaries from config nodes."""
        boundaries = {}
        
        for node in config_nodes:
            if node.attributes.get("config_type") == ConfigNodeType.ETHICAL_BOUNDARIES.value:
                boundaries.update(node.attributes.get("values", {}))
        
        return boundaries
    
    def _extract_current_trust_parameters(self, config_nodes: List[GraphNode]) -> Dict[str, Any]:
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
        baseline_patterns: Dict[str, Any],
        current_patterns: Dict[str, Any]
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