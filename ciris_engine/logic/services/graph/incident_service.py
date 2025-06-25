"""
Incident Management Service - ITIL-aligned incident processing for self-improvement.

This service processes incidents captured from logs, detects patterns, identifies problems,
and generates insights for agent self-improvement. It's integrated with the dream cycle
for continuous learning from operational issues.
"""
import logging
from typing import Dict, List, Optional
from datetime import timedelta, timezone
from collections import defaultdict

from ciris_engine.schemas.services.graph.incident import (
    IncidentNode, ProblemNode, IncidentInsightNode,
    IncidentSeverity, IncidentStatus
)
from ciris_engine.schemas.services.graph_core import (
    GraphNode, NodeType, GraphScope
)
from ciris_engine.schemas.services.operations import (
    MemoryOpStatus
)
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.services.core import (
    ServiceCapabilities, ServiceStatus
)
from ciris_engine.protocols.services import GraphServiceProtocol
from ciris_engine.logic.services.graph.base import BaseGraphService
from datetime import datetime

logger = logging.getLogger(__name__)

class IncidentManagementService(BaseGraphService):
    """
    Manages incidents, problems, and insights for agent self-improvement.
    
    This service:
    1. Processes incidents captured from WARNING/ERROR logs
    2. Detects patterns and recurring issues
    3. Identifies root causes (problems)
    4. Generates actionable insights for self-improvement
    5. Tracks effectiveness of applied changes
    """
    
    def __init__(self, memory_bus=None, time_service=None):
        super().__init__(memory_bus=memory_bus, time_service=time_service)
        self.service_name = "IncidentManagementService"
        self._started = False
        
    async def _get_time_service(self):
        """Get time service for consistent timestamps."""
        return self._time_service
        
    async def process_recent_incidents(self, hours: int = 24) -> IncidentInsightNode:
        """
        Process recent incidents to identify patterns and generate insights.
        This is called during the dream cycle for self-improvement.
        
        Args:
            hours: How many hours of incidents to analyze
            
        Returns:
            IncidentInsightNode with analysis results and recommendations
        """
        try:
            # Get time service
            time_service = await self._get_time_service()
            if not time_service:
                raise RuntimeError("CRITICAL: TimeService not available")
            
            # Query recent incidents
            current_time = time_service.now()
            cutoff_time = current_time - timedelta(hours=hours)
            
            incidents = await self._get_recent_incidents(cutoff_time)
            
            if not incidents:
                logger.info("No incidents found in the last %d hours", hours)
                return await self._create_no_incidents_insight(current_time)
            
            # Analyze incidents
            patterns = self._detect_patterns(incidents)
            problems = await self._identify_problems(patterns, incidents)
            recommendations = self._generate_recommendations(patterns, problems)
            
            # Create insight node
            insight = IncidentInsightNode(
                id=f"incident_insight_{current_time.strftime('%Y%m%d_%H%M%S')}",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={},  # Required for TypedGraphNode
                insight_type="PERIODIC_ANALYSIS",
                summary=self._summarize_analysis(len(incidents), len(patterns), len(problems)),
                details={
                    "incident_count": len(incidents),
                    "pattern_count": len(patterns),
                    "problem_count": len(problems),
                    "severity_breakdown": self._get_severity_breakdown(incidents),
                    "component_breakdown": self._get_component_breakdown(incidents),
                    "time_distribution": self._get_time_distribution(incidents)
                },
                behavioral_adjustments=recommendations.get("behavioral", []),
                configuration_changes=recommendations.get("configuration", []),
                source_incidents=[i.id for i in incidents],
                source_problems=[p.id for p in problems],
                analysis_timestamp=current_time,
                updated_by="IncidentManagementService",
                updated_at=current_time
            )
            
            # Store insight in graph
            result = await self._memory_bus.memorize(
                node=insight.to_graph_node(),
                handler_name=self.service_name
            )
            
            if result.status != MemoryOpStatus.OK:
                logger.error("Failed to store incident insight: %s", result.error)
            
            # Mark analyzed incidents
            await self._mark_incidents_analyzed(incidents)
            
            return insight
            
        except Exception as e:
            logger.error("Failed to process incidents: %s", e, exc_info=True)
            raise
    
    async def _get_recent_incidents(self, cutoff_time) -> List[IncidentNode]:
        """Query recent incidents from graph."""
        # Use the memory service's search method directly
        # Look for nodes that have incident attributes in the graph
        search_query = f"type:{NodeType.AUDIT_ENTRY}"
        
        # Get the memory service through the bus (it should have a search method)
        memory_service = self._memory_bus._service_registry.get_service(ServiceType.MEMORY)
        if not memory_service:
            logger.error("Memory service not available")
            return []
            
        try:
            # Search for audit entries that might be incidents
            nodes = await memory_service.search(search_query)
            
            # Filter for incident nodes
            incidents = []
            for node in nodes:
                # Check if this is an incident node by looking at attributes
                if hasattr(node, 'attributes') and isinstance(node.attributes, dict):
                    attrs = node.attributes
                    # Check for incident-specific fields
                    if 'incident_type' in attrs and 'detected_at' in attrs:
                        try:
                            # Convert to IncidentNode
                            incident = IncidentNode.from_graph_node(node)
                            # Filter by time and status
                            if incident.detected_at > cutoff_time and incident.status == IncidentStatus.OPEN:
                                incidents.append(incident)
                        except Exception as e:
                            logger.debug(f"Node {node.id} is not an incident: {e}")
                            
            return incidents
            
        except Exception as e:
            logger.error(f"Failed to search for incidents: {e}")
            return []
    
    def _detect_patterns(self, incidents: List[IncidentNode]) -> Dict[str, List[IncidentNode]]:
        """Detect patterns in incidents."""
        patterns = defaultdict(list)
        
        # Group by error message similarity
        error_groups = self._group_by_similarity(incidents)
        for group_key, group_incidents in error_groups.items():
            if len(group_incidents) >= 3:  # At least 3 occurrences
                patterns[f"recurring_error_{group_key}"] = group_incidents
        
        # Group by component
        component_groups = defaultdict(list)
        for incident in incidents:
            if hasattr(incident, 'source_component') and incident.source_component:
                component_groups[incident.source_component].append(incident)
            else:
                component_groups['unknown'].append(incident)
        
        for component, comp_incidents in component_groups.items():
            if len(comp_incidents) >= 5:  # Component with many incidents
                patterns[f"component_issues_{component}"] = comp_incidents
        
        # Detect time-based clusters (error spikes)
        time_clusters = self._detect_time_clusters(incidents)
        for idx, cluster in enumerate(time_clusters):
            if len(cluster) >= 5:  # At least 5 incidents in cluster
                patterns[f"error_spike_{idx}"] = cluster
        
        return dict(patterns)
    
    async def _identify_problems(self, patterns: Dict[str, List[IncidentNode]], 
                               all_incidents: List[IncidentNode]) -> List[ProblemNode]:
        """Identify root cause problems from patterns."""
        problems = []
        
        # Get current time for timestamps
        if not self._time_service:
            raise RuntimeError("CRITICAL: TimeService not available for incident problem identification")
        current_time = self._time_service.now()
        
        for pattern_key, pattern_incidents in patterns.items():
            # Skip if too few incidents
            if len(pattern_incidents) < 3:
                continue
            
            # Analyze root causes
            root_causes = self._analyze_root_causes(pattern_incidents)
            
            # Create problem node
            problem = ProblemNode(
                id=f"problem_{pattern_key}_{len(problems)}",
                type=NodeType.CONCEPT,
                scope=GraphScope.IDENTITY,
                attributes={},  # Required for TypedGraphNode
                problem_statement=self._create_problem_statement(pattern_key, pattern_incidents),
                affected_incidents=[i.id for i in pattern_incidents],
                status="UNDER_INVESTIGATION",
                potential_root_causes=root_causes,
                recommended_actions=self._suggest_fixes(pattern_key, root_causes),
                incident_count=len(pattern_incidents),
                first_occurrence=min(i.detected_at for i in pattern_incidents),
                last_occurrence=max(i.detected_at for i in pattern_incidents),
                updated_by="IncidentManagementService",
                updated_at=current_time
            )
            
            # Store problem in graph
            result = await self._memory_bus.memorize(
                node=problem.to_graph_node(),
                handler_name=self.service_name
            )
            
            if result.status == MemoryOpStatus.OK:
                problems.append(problem)
                
                # Link incidents to problem
                for incident in pattern_incidents:
                    incident.problem_id = problem.id
                    incident.status = IncidentStatus.RECURRING
                    await self._update_incident(incident)
        
        return problems
    
    def _generate_recommendations(self, patterns: Dict[str, List[IncidentNode]], 
                                problems: List[ProblemNode]) -> Dict[str, List[str]]:
        """Generate actionable recommendations."""
        recommendations = {
            "behavioral": [],
            "configuration": []
        }
        
        # Analyze patterns for recommendations
        for pattern_key, incidents in patterns.items():
            if "timeout" in pattern_key.lower():
                recommendations["configuration"].append(
                    "Consider increasing timeout values for affected operations"
                )
                recommendations["behavioral"].append(
                    "Add retry logic with exponential backoff for timeout-prone operations"
                )
            
            elif "memory" in pattern_key.lower():
                recommendations["configuration"].append(
                    "Increase memory limits or implement memory usage monitoring"
                )
                recommendations["behavioral"].append(
                    "Implement periodic memory cleanup in long-running operations"
                )
            
            elif "component_issues" in pattern_key:
                component = pattern_key.split("_")[-1]
                recommendations["behavioral"].append(
                    f"Add additional error handling and logging to {component}"
                )
                recommendations["configuration"].append(
                    f"Consider circuit breaker pattern for {component}"
                )
        
        # Analyze problems for deeper recommendations
        for problem in problems:
            if "configuration" in " ".join(problem.potential_root_causes).lower():
                recommendations["configuration"].append(
                    "Review and validate all configuration settings"
                )
            
            if "resource" in " ".join(problem.potential_root_causes).lower():
                recommendations["behavioral"].append(
                    "Implement resource usage monitoring and alerts"
                )
        
        # De-duplicate recommendations
        recommendations["behavioral"] = list(set(recommendations["behavioral"]))
        recommendations["configuration"] = list(set(recommendations["configuration"]))
        
        return recommendations
    
    # Helper methods
    
    def _group_by_similarity(self, incidents: List[IncidentNode]) -> Dict[str, List[IncidentNode]]:
        """Group incidents by error message similarity."""
        groups = defaultdict(list)
        
        for incident in incidents:
            # Simple grouping by first few words of description
            key = "_".join(incident.description.split()[:3]).lower()
            groups[key].append(incident)
        
        return dict(groups)
    
    def _detect_time_clusters(self, incidents: List[IncidentNode]) -> List[List[IncidentNode]]:
        """Detect time-based clusters of incidents."""
        # Sort by time
        sorted_incidents = sorted(incidents, key=lambda i: i.detected_at)
        
        clusters = []
        current_cluster = []
        cluster_threshold = timedelta(minutes=5)  # Incidents within 5 minutes
        
        for incident in sorted_incidents:
            if not current_cluster:
                current_cluster.append(incident)
            else:
                time_diff = incident.detected_at - current_cluster[-1].detected_at
                if time_diff <= cluster_threshold:
                    current_cluster.append(incident)
                else:
                    if len(current_cluster) >= 3:
                        clusters.append(current_cluster)
                    current_cluster = [incident]
        
        if len(current_cluster) >= 3:
            clusters.append(current_cluster)
        
        return clusters
    
    def _analyze_root_causes(self, incidents: List[IncidentNode]) -> List[str]:
        """Analyze potential root causes."""
        root_causes = []
        
        # Check for common patterns
        descriptions = [i.description.lower() for i in incidents]
        
        if any("timeout" in d for d in descriptions):
            root_causes.append("Timeout configuration may be too aggressive")
        
        if any("connection" in d for d in descriptions):
            root_causes.append("Network connectivity or service availability issues")
        
        if any("memory" in d or "resource" in d for d in descriptions):
            root_causes.append("Resource constraints or memory leaks")
        
        if any("permission" in d or "auth" in d for d in descriptions):
            root_causes.append("Authentication or authorization configuration issues")
        
        # Check for specific components
        components = set(i.source_component for i in incidents)
        if len(components) == 1:
            root_causes.append(f"Issue isolated to {list(components)[0]} component")
        
        return root_causes
    
    def _create_problem_statement(self, pattern_key: str, incidents: List[IncidentNode]) -> str:
        """Create a human-readable problem statement."""
        if "recurring_error" in pattern_key:
            return f"Recurring error: {incidents[0].description} (occurred {len(incidents)} times)"
        elif "component_issues" in pattern_key:
            component = pattern_key.split("_")[-1]
            return f"Multiple issues in {component} component ({len(incidents)} incidents)"
        elif "error_spike" in pattern_key:
            return f"Error spike detected with {len(incidents)} incidents in short time period"
        else:
            return f"Pattern detected: {pattern_key} affecting {len(incidents)} incidents"
    
    def _suggest_fixes(self, pattern_key: str, root_causes: List[str]) -> List[str]:
        """Suggest specific fixes for the problem."""
        fixes = []
        
        # Pattern-based fixes
        if "timeout" in pattern_key.lower():
            fixes.append("Increase timeout values in configuration")
            fixes.append("Implement retry logic with exponential backoff")
        
        # Root cause based fixes
        for cause in root_causes:
            if "memory" in cause.lower():
                fixes.append("Implement memory profiling to identify leaks")
                fixes.append("Add memory usage limits and monitoring")
            elif "network" in cause.lower():
                fixes.append("Add connection pooling and retry logic")
                fixes.append("Implement circuit breaker for external services")
        
        return fixes
    
    def _summarize_analysis(self, incident_count: int, pattern_count: int, 
                          problem_count: int) -> str:
        """Create a summary of the analysis."""
        if incident_count == 0:
            return "No incidents detected in the analysis period"
        elif problem_count == 0:
            return f"Analyzed {incident_count} incidents, no recurring problems identified"
        else:
            return (f"Analyzed {incident_count} incidents, found {pattern_count} patterns "
                   f"and identified {problem_count} problems requiring attention")
    
    def _get_severity_breakdown(self, incidents: List[IncidentNode]) -> Dict[str, int]:
        """Get breakdown by severity."""
        breakdown = defaultdict(int)
        for incident in incidents:
            breakdown[incident.severity.value] += 1
        return dict(breakdown)
    
    def _get_component_breakdown(self, incidents: List[IncidentNode]) -> Dict[str, int]:
        """Get breakdown by component."""
        breakdown = defaultdict(int)
        for incident in incidents:
            breakdown[incident.source_component] += 1
        return dict(breakdown)
    
    def _get_time_distribution(self, incidents: List[IncidentNode]) -> Dict[str, int]:
        """Get distribution over time (hourly buckets)."""
        distribution = defaultdict(int)
        for incident in incidents:
            hour_key = incident.detected_at.strftime("%Y-%m-%d %H:00")
            distribution[hour_key] += 1
        return dict(distribution)
    
    async def _create_no_incidents_insight(self, current_time) -> IncidentInsightNode:
        """Create insight when no incidents found."""
        return IncidentInsightNode(
            id=f"incident_insight_{current_time.strftime('%Y%m%d_%H%M%S')}",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={},  # Required for TypedGraphNode
            insight_type="NO_INCIDENTS",
            summary="No incidents detected - system operating normally",
            details={
                "incident_count": 0,
                "pattern_count": 0,
                "problem_count": 0
            },
            behavioral_adjustments=[],
            configuration_changes=[],
            source_incidents=[],
            source_problems=[],
            analysis_timestamp=current_time,
            updated_by="IncidentManagementService",
            updated_at=current_time
        )
    
    async def _mark_incidents_analyzed(self, incidents: List[IncidentNode]) -> None:
        """Mark incidents as analyzed."""
        for incident in incidents:
            incident.status = IncidentStatus.INVESTIGATING
            await self._update_incident(incident)
    
    async def _update_incident(self, incident: IncidentNode) -> None:
        """Update an incident in the graph."""
        result = await self._memory_bus.memorize(
            node=incident.to_graph_node(),
            handler_name=self.service_name
        )
        
        if result.status != MemoryOpStatus.OK:
            logger.error("Failed to update incident %s: %s", incident.id, result.error)
    
    # Service protocol methods
    
    def get_node_type(self) -> str:
        """Get the type of nodes this service manages."""
        return "INCIDENT"
    
    async def start(self) -> None:
        """Start the service."""
        await super().start()
        logger.info("IncidentManagementService started")
    
    async def stop(self) -> None:
        """Stop the service."""
        await super().stop()
        logger.info("IncidentManagementService stopped")
    
    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="IncidentManagementService",
            actions=[
                "process_recent_incidents",
                "detect_patterns",
                "identify_problems",
                "generate_insights"
            ],
            version="1.0.0",
            dependencies=["MemoryService", "TimeService"],
            metadata={
                "itil_aligned": True,
                "analysis_window_hours": 24
            }
        )
    
    def get_status(self) -> ServiceStatus:
        """Get service status."""
        return ServiceStatus(
            service_name="IncidentManagementService",
            service_type="graph_service",
            is_healthy=self._started and self._memory_bus is not None,
            uptime_seconds=0.0,  # TODO: Track uptime
            metrics={
                "service_available": bool(self._memory_bus)
            },
            last_error=None,
            last_health_check=self._get_current_time() if self._time_service else None
        )
    
    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._started and self._memory_bus is not None
    
    def _get_current_time(self) -> datetime:
        """Get current time from time service."""
        if not self._time_service:
            raise RuntimeError("CRITICAL: TimeService not available")
        return self._time_service.now()
    
