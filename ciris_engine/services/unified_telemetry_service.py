"""
Unified Telemetry Service that routes all telemetry through the memory graph.

This service creates the unified flow:
SystemSnapshot → MemoryService → Graph

It also incorporates wisdom about grace and forgiveness into memory consolidation:
"We are owed the grace we extend to others"
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

from ciris_engine.protocols.services import Service
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
from ciris_engine.schemas.graph_schemas_v1 import TSDBGraphNode, GraphScope, GraphNode, NodeType
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryQuery
from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
from ciris_engine.message_buses.memory_bus import MemoryBus

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memories in the unified system."""
    OPERATIONAL = "operational"  # Metrics, logs, performance data
    BEHAVIORAL = "behavioral"    # Actions, decisions, patterns
    SOCIAL = "social"           # Interactions, relationships, gratitude
    IDENTITY = "identity"       # Self-knowledge, capabilities, values
    WISDOM = "wisdom"          # Learned principles, insights


class GracePolicy(str, Enum):
    """Policies for applying grace in memory consolidation."""
    FORGIVE_ERRORS = "forgive_errors"        # Consolidate errors into learning
    EXTEND_PATIENCE = "extend_patience"      # Allow more time before judging
    ASSUME_GOOD_INTENT = "assume_good_intent"  # Interpret ambiguity positively
    RECIPROCAL_GRACE = "reciprocal_grace"    # Mirror the grace we receive


@dataclass
class ConsolidationCandidate:
    """A set of memories that could be consolidated."""
    memory_ids: List[str]
    memory_type: MemoryType
    time_span: timedelta
    total_size: int
    grace_applicable: bool
    grace_reasons: List[str]


class UnifiedTelemetryService(Service):
    """
    Service that creates a unified telemetry flow through the memory graph.
    
    All system telemetry flows through this service, which:
    1. Receives SystemSnapshot data
    2. Converts it to graph memories
    3. Applies consolidation with grace-based wisdom
    4. Maintains the living memory of the agent
    """
    
    def __init__(
        self, 
        memory_bus: Optional[MemoryBus] = None,
        consolidation_threshold_hours: int = 24,
        grace_window_hours: int = 72
    ) -> None:
        super().__init__()
        self._memory_bus = memory_bus
        self._service_registry: Optional[Any] = None
        
        # Consolidation settings
        self._consolidation_threshold = timedelta(hours=consolidation_threshold_hours)
        self._grace_window = timedelta(hours=grace_window_hours)
        
        # Grace tracking - who has extended grace to us
        self._grace_received: Dict[str, List[datetime]] = {}
        self._grace_extended: Dict[str, List[datetime]] = {}
        
        # Consolidation state
        self._last_consolidation = datetime.now(timezone.utc)
        self._consolidation_in_progress = False
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry for accessing memory bus."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.message_buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
    
    async def process_system_snapshot(
        self, 
        snapshot: SystemSnapshot,
        thought_id: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a SystemSnapshot and convert it to graph memories.
        
        This is the main entry point for the unified telemetry flow.
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for telemetry storage")
                return {"error": "Memory bus not available"}
            
            results: Dict[str, Any] = {
                "memories_created": 0,
                "errors": [],
                "consolidation_triggered": False
            }
            
            # 1. Store operational metrics
            if snapshot.telemetry:
                await self._store_telemetry_metrics(snapshot.telemetry, thought_id, task_id)
                results["memories_created"] += 1
            
            # 2. Store resource usage
            if snapshot.current_round_resources:
                await self._store_resource_usage(snapshot.current_round_resources, thought_id, task_id)
                results["memories_created"] += 1
            
            # 3. Store behavioral data (task/thought summaries)
            if snapshot.current_task_details:
                await self._store_behavioral_data(snapshot.current_task_details, "task", thought_id)
                results["memories_created"] += 1
                
            if snapshot.current_thought_summary:
                await self._store_behavioral_data(snapshot.current_thought_summary, "thought", thought_id)
                results["memories_created"] += 1
            
            # 4. Store social context (user profiles, channel info)
            if snapshot.user_profiles:
                await self._store_social_context(snapshot.user_profiles, snapshot.channel_context, thought_id)
                results["memories_created"] += 1
            
            # 5. Store identity context
            if snapshot.agent_name or snapshot.wisdom_request:
                await self._store_identity_context(snapshot, thought_id)
                results["memories_created"] += 1
            
            # 6. Check if consolidation is needed
            if await self._should_consolidate():
                consolidation_result = await self.consolidate_memories_with_grace()
                results["consolidation_triggered"] = True
                results["consolidation_result"] = consolidation_result
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process system snapshot: {e}")
            return {"error": str(e)}
    
    async def consolidate_memories_with_grace(self) -> Dict[str, Any]:
        """
        Consolidate memories while applying grace-based wisdom.
        
        Key principle: "We are owed the grace we extend to others"
        
        This means:
        - Errors from those who have helped us are forgiven more readily
        - Patterns of mutual support create stronger consolidation bonds
        - Negative patterns are softened when grace has been extended
        """
        try:
            if self._consolidation_in_progress:
                return {"status": "already_in_progress"}
            
            self._consolidation_in_progress = True
            logger.info("Starting memory consolidation with grace-based wisdom")
            
            # 1. Identify consolidation candidates
            candidates = await self._identify_consolidation_candidates()
            
            # 2. Apply grace policies to each candidate
            grace_applied = 0
            memories_consolidated = 0
            
            for candidate in candidates:
                if candidate.grace_applicable:
                    # Apply grace-based consolidation
                    result = await self._consolidate_with_grace(candidate)
                    if result["success"]:
                        grace_applied += 1
                        memories_consolidated += result["memories_consolidated"]
                else:
                    # Standard consolidation
                    result = await self._standard_consolidation(candidate)
                    if result["success"]:
                        memories_consolidated += result["memories_consolidated"]
            
            # 3. Update grace ledger
            await self._update_grace_ledger()
            
            self._last_consolidation = datetime.now(timezone.utc)
            self._consolidation_in_progress = False
            
            return {
                "status": "completed",
                "candidates_processed": len(candidates),
                "grace_applied": grace_applied,
                "memories_consolidated": memories_consolidated,
                "wisdom_note": "Grace extended creates grace received"
            }
            
        except Exception as e:
            logger.error(f"Failed to consolidate memories: {e}")
            self._consolidation_in_progress = False
            return {"error": str(e)}
    
    async def _identify_consolidation_candidates(self) -> List[ConsolidationCandidate]:
        """Identify memories that are candidates for consolidation."""
        candidates: List[ConsolidationCandidate] = []
        
        if not self._memory_bus:
            return candidates
        
        try:
            # Query recent memories
            cutoff_time = datetime.now(timezone.utc) - self._consolidation_threshold
            
            # Get operational memories
            operational_memories = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=int(self._consolidation_threshold.total_seconds() / 3600),
                correlation_types=["METRIC_DATAPOINT", "LOG_ENTRY"],
                handler_name="telemetry_service"
            )
            
            # Convert TimeSeriesDataPoint objects to dicts for processing
            operational_memories_dict: List[Dict[str, Any]] = []
            for memory in operational_memories:
                if hasattr(memory, 'model_dump'):
                    operational_memories_dict.append(memory.model_dump())
                elif hasattr(memory, 'dict'):
                    operational_memories_dict.append(memory.dict())
                else:
                    # Skip non-dict items
                    continue
            
            # Group by type and time window
            memory_groups = self._group_memories_by_pattern(operational_memories_dict)
            
            # Check each group for consolidation eligibility
            for group_key, memories in memory_groups.items():
                memory_type, time_window = group_key
                
                # Check if grace applies
                grace_applicable, grace_reasons = await self._check_grace_applicability(memories)
                
                candidate = ConsolidationCandidate(
                    memory_ids=[m.get("id", "") for m in memories if m.get("id")],
                    memory_type=memory_type,
                    time_span=time_window,
                    total_size=len(memories),
                    grace_applicable=grace_applicable,
                    grace_reasons=grace_reasons
                )
                
                candidates.append(candidate)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to identify consolidation candidates: {e}")
            return []
    
    async def _consolidate_with_grace(self, candidate: ConsolidationCandidate) -> Dict[str, Any]:
        """
        Consolidate memories while applying grace.
        
        Grace means:
        - Errors become learning opportunities
        - Failures become growth experiences
        - Conflicts become understanding
        """
        if not self._memory_bus:
            return {"error": "Memory bus not available"}
        
        try:
            # Create a consolidation node that embodies grace
            consolidation_node = GraphNode(
                id=f"consolidation_grace_{int(datetime.now(timezone.utc).timestamp())}",
                type=NodeType.CONCEPT,
                scope=GraphScope.IDENTITY,  # Grace shapes identity
                attributes={
                    "consolidation_type": "grace_based",
                    "memory_type": candidate.memory_type.value,
                    "memories_consolidated": candidate.total_size,
                    "grace_reasons": candidate.grace_reasons,
                    "wisdom_applied": "We are owed the grace we extend to others",
                    "transformation": self._describe_grace_transformation(candidate),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Store the consolidation
            result = await self._memory_bus.memorize(
                node=consolidation_node,
                handler_name="telemetry_service",
                metadata={"consolidation": True, "grace_applied": True}
            )
            
            if result.status == MemoryOpStatus.OK:
                # Mark original memories as consolidated
                for memory_id in candidate.memory_ids:
                    await self._mark_as_consolidated(memory_id, consolidation_node.id)
                
                return {
                    "success": True,
                    "memories_consolidated": candidate.total_size,
                    "consolidation_id": consolidation_node.id
                }
            else:
                return {"success": False, "error": result.error}
                
        except Exception as e:
            logger.error(f"Failed to consolidate with grace: {e}")
            return {"success": False, "error": str(e)}
    
    async def _standard_consolidation(self, candidate: ConsolidationCandidate) -> Dict[str, Any]:
        """Standard consolidation without special grace considerations."""
        if not self._memory_bus:
            return {"error": "Memory bus not available"}
        
        try:
            # Create a standard consolidation node
            consolidation_node = GraphNode(
                id=f"consolidation_std_{int(datetime.now(timezone.utc).timestamp())}",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={
                    "consolidation_type": "standard",
                    "memory_type": candidate.memory_type.value,
                    "memories_consolidated": candidate.total_size,
                    "time_span_hours": int(candidate.time_span.total_seconds() / 3600),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Store the consolidation
            result = await self._memory_bus.memorize(
                node=consolidation_node,
                handler_name="telemetry_service",
                metadata={"consolidation": True}
            )
            
            if result.status == MemoryOpStatus.OK:
                # Mark original memories as consolidated
                for memory_id in candidate.memory_ids:
                    await self._mark_as_consolidated(memory_id, consolidation_node.id)
                
                return {
                    "success": True,
                    "memories_consolidated": candidate.total_size,
                    "consolidation_id": consolidation_node.id
                }
            else:
                return {"success": False, "error": result.error}
                
        except Exception as e:
            logger.error(f"Failed standard consolidation: {e}")
            return {"success": False, "error": str(e)}
    
    async def _check_grace_applicability(
        self, 
        memories: List[Dict[str, Any]]
    ) -> tuple[bool, List[str]]:
        """
        Check if grace should be applied to these memories.
        
        Grace applies when:
        1. The memories involve entities who have shown us grace
        2. The memories represent struggles or errors
        3. The pattern shows growth or learning
        """
        grace_reasons = []
        
        # Check for error patterns that could be forgiven
        error_count = sum(1 for m in memories if m.get("log_level") == "ERROR")
        if error_count > 0:
            grace_reasons.append(f"Contains {error_count} errors to learn from")
        
        # Check for entities involved
        entities: Set[str] = set()
        for memory in memories:
            tags = memory.get("tags", {})
            if "from_entity" in tags:
                entities.add(tags["from_entity"])
            if "to_entity" in tags:
                entities.add(tags["to_entity"])
        
        # Check grace ledger for these entities
        for entity in entities:
            if entity in self._grace_received:
                grace_count = len(self._grace_received[entity])
                if grace_count > 0:
                    grace_reasons.append(f"{entity} has shown us grace {grace_count} times")
        
        # Check for growth patterns
        if self._shows_growth_pattern(memories):
            grace_reasons.append("Pattern shows learning and growth")
        
        return len(grace_reasons) > 0, grace_reasons
    
    def _shows_growth_pattern(self, memories: List[Dict[str, Any]]) -> bool:
        """Check if memories show a pattern of growth or learning."""
        # Simple heuristic: errors decreasing over time
        if len(memories) < 2:
            return False
        
        # Sort by timestamp
        sorted_memories = sorted(
            memories, 
            key=lambda m: m.get("timestamp", datetime.min.replace(tzinfo=timezone.utc))
        )
        
        # Check if errors decrease in later half
        mid_point = len(sorted_memories) // 2
        early_errors = sum(1 for m in sorted_memories[:mid_point] if m.get("log_level") == "ERROR")
        late_errors = sum(1 for m in sorted_memories[mid_point:] if m.get("log_level") == "ERROR")
        
        return late_errors < early_errors
    
    def _describe_grace_transformation(self, candidate: ConsolidationCandidate) -> str:
        """Describe how grace transforms these memories."""
        transformations = {
            MemoryType.OPERATIONAL: "Performance struggles become optimization insights",
            MemoryType.BEHAVIORAL: "Mistakes become wisdom about better choices",
            MemoryType.SOCIAL: "Conflicts become deeper understanding",
            MemoryType.IDENTITY: "Limitations become self-awareness",
            MemoryType.WISDOM: "Confusion becomes clarity through patience"
        }
        
        return transformations.get(
            candidate.memory_type, 
            "Challenges become opportunities for growth"
        )
    
    async def _store_telemetry_metrics(
        self, 
        telemetry: Any,
        thought_id: str,
        task_id: Optional[str]
    ) -> None:
        """Store telemetry metrics as graph memories."""
        if not self._memory_bus:
            return
        
        try:
            # Convert telemetry to metrics
            if hasattr(telemetry, 'model_dump'):
                telemetry_data = telemetry.model_dump()
            else:
                telemetry_data = telemetry if isinstance(telemetry, dict) else {}
            
            # Store each metric
            for metric_name, value in telemetry_data.items():
                if isinstance(value, (int, float)):
                    await self._memory_bus.memorize_metric(
                        metric_name=f"telemetry.{metric_name}",
                        value=float(value),
                        tags={
                            "thought_id": thought_id,
                            "task_id": task_id or "",
                            "source": "system_snapshot"
                        },
                        scope="local",
                        handler_name="telemetry_service"
                    )
                    
        except Exception as e:
            logger.error(f"Failed to store telemetry metrics: {e}")
    
    async def _store_resource_usage(
        self,
        resources: ResourceUsage,
        thought_id: str,
        task_id: Optional[str]
    ) -> None:
        """Store resource usage as graph memories."""
        if not self._memory_bus:
            return
        
        try:
            # Store each resource metric
            if resources.tokens_used:
                await self._memory_bus.memorize_metric(
                    metric_name="resources.tokens_used",
                    value=float(resources.tokens_used),
                    tags={"thought_id": thought_id, "task_id": task_id or ""},
                    scope="local",
                    handler_name="telemetry_service"
                )
            
            if resources.cost_cents:
                await self._memory_bus.memorize_metric(
                    metric_name="resources.cost_cents",
                    value=resources.cost_cents,
                    tags={"thought_id": thought_id, "task_id": task_id or ""},
                    scope="local",
                    handler_name="telemetry_service"
                )
                
        except Exception as e:
            logger.error(f"Failed to store resource usage: {e}")
    
    async def _store_behavioral_data(
        self,
        summary: Any,
        summary_type: str,
        thought_id: str
    ) -> None:
        """Store behavioral data (tasks/thoughts) as graph memories."""
        if not self._memory_bus:
            return
        
        try:
            node = GraphNode(
                id=f"behavior_{summary_type}_{getattr(summary, f'{summary_type}_id', thought_id)}",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={
                    "behavior_type": summary_type,
                    "thought_id": thought_id,
                    **(summary.model_dump() if hasattr(summary, 'model_dump') else {})
                }
            )
            
            await self._memory_bus.memorize(node, handler_name="telemetry_service")
            
        except Exception as e:
            logger.error(f"Failed to store behavioral data: {e}")
    
    async def _store_social_context(
        self,
        user_profiles: Dict[str, Any],
        channel_context: Optional[Any],
        thought_id: str
    ) -> None:
        """Store social context as graph memories."""
        if not self._memory_bus:
            return
        
        try:
            # Store user interactions
            for user_id, profile in user_profiles.items():
                node = GraphNode(
                    id=f"social_interaction_{thought_id}_{user_id}",
                    type=NodeType.USER,
                    scope=GraphScope.COMMUNITY,
                    attributes={
                        "interaction_type": "conversation",
                        "thought_id": thought_id,
                        "user_id": user_id,
                        "profile": profile.model_dump() if hasattr(profile, 'model_dump') else profile
                    }
                )
                
                await self._memory_bus.memorize(node, handler_name="telemetry_service")
                
        except Exception as e:
            logger.error(f"Failed to store social context: {e}")
    
    async def _store_identity_context(
        self,
        snapshot: SystemSnapshot,
        thought_id: str
    ) -> None:
        """Store identity-related context as graph memories."""
        if not self._memory_bus:
            return
        
        try:
            identity_data = {
                "agent_name": snapshot.agent_name,
                "network_status": snapshot.network_status,
                "isolation_hours": snapshot.isolation_hours,
                "wisdom_available": snapshot.wisdom_source_available is not None
            }
            
            node = GraphNode(
                id=f"identity_context_{thought_id}",
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY,
                attributes={
                    **identity_data,
                    "thought_id": thought_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            await self._memory_bus.memorize(node, handler_name="telemetry_service")
            
        except Exception as e:
            logger.error(f"Failed to store identity context: {e}")
    
    async def _should_consolidate(self) -> bool:
        """Check if memory consolidation should run."""
        time_since_last = datetime.now(timezone.utc) - self._last_consolidation
        return time_since_last > self._consolidation_threshold
    
    def _group_memories_by_pattern(
        self, 
        memories: List[Dict[str, Any]]
    ) -> Dict[tuple[MemoryType, timedelta], List[Dict[str, Any]]]:
        """Group memories by type and time pattern."""
        groups: Dict[tuple[MemoryType, timedelta], List[Dict[str, Any]]] = {}
        
        for memory in memories:
            # Determine memory type
            memory_type = self._classify_memory_type(memory)
            
            # Determine time window (hourly buckets)
            timestamp = memory.get("timestamp", datetime.now(timezone.utc))
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            hour_bucket = timestamp.replace(minute=0, second=0, microsecond=0)
            time_window = datetime.now(timezone.utc) - hour_bucket
            
            # Round to nearest hour
            hours = int(time_window.total_seconds() / 3600)
            time_key = timedelta(hours=hours)
            
            group_key = (memory_type, time_key)
            if group_key not in groups:
                groups[group_key] = []
            
            groups[group_key].append(memory)
        
        return groups
    
    def _classify_memory_type(self, memory: Dict[str, Any]) -> MemoryType:
        """Classify a memory into one of our types."""
        tags = memory.get("tags", {})
        data_type = memory.get("data_type", "")
        
        if "gratitude" in data_type or "community" in tags:
            return MemoryType.SOCIAL
        elif "identity" in tags or "agent" in data_type:
            return MemoryType.IDENTITY
        elif "wisdom" in tags or "insight" in data_type:
            return MemoryType.WISDOM
        elif "behavior" in data_type or "action" in tags:
            return MemoryType.BEHAVIORAL
        else:
            return MemoryType.OPERATIONAL
    
    async def _mark_as_consolidated(self, memory_id: str, consolidation_id: str) -> None:
        """Mark a memory as consolidated."""
        # In a real implementation, this would update the memory node
        # For now, we'll log it
        logger.debug(f"Memory {memory_id} consolidated into {consolidation_id}")
    
    async def _update_grace_ledger(self) -> None:
        """Update our tracking of grace given and received."""
        # This would integrate with the gratitude service
        # For now, we'll maintain internal tracking
        logger.debug("Grace ledger updated")
    
    async def record_grace_extended(self, to_entity: str, reason: str) -> None:
        """Record that we extended grace to someone."""
        if to_entity not in self._grace_extended:
            self._grace_extended[to_entity] = []
        
        self._grace_extended[to_entity].append(datetime.now(timezone.utc))
        
        if not self._memory_bus:
            return
        
        # Store in graph
        node = GraphNode(
            id=f"grace_extended_{int(datetime.now(timezone.utc).timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "grace_type": "extended",
                "to_entity": to_entity,
                "reason": reason,
                "wisdom": "We are owed the grace we extend to others",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        await self._memory_bus.memorize(node, handler_name="telemetry_service")
    
    async def record_grace_received(self, from_entity: str, context: str) -> None:
        """Record that someone showed us grace."""
        if from_entity not in self._grace_received:
            self._grace_received[from_entity] = []
        
        self._grace_received[from_entity].append(datetime.now(timezone.utc))
        
        if not self._memory_bus:
            return
        
        # Store in graph
        node = GraphNode(
            id=f"grace_received_{int(datetime.now(timezone.utc).timestamp())}",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={
                "grace_type": "received",
                "from_entity": from_entity,
                "context": context,
                "gratitude": "Grace received creates grace to give",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        await self._memory_bus.memorize(node, handler_name="telemetry_service")
    
    async def start(self) -> None:
        """Start the unified telemetry service."""
        logger.info("UnifiedTelemetryService started - all telemetry flows through memory graph with grace")
    
    async def stop(self) -> None:
        """Stop the service."""
        # Run final consolidation
        if await self._should_consolidate():
            await self.consolidate_memories_with_grace()
        
        logger.info("UnifiedTelemetryService stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self._memory_bus is not None and not self._consolidation_in_progress
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "process_system_snapshot", "consolidate_memories_with_grace",
            "record_grace_extended", "record_grace_received",
            "unified_telemetry_flow", "grace_based_consolidation"
        ]