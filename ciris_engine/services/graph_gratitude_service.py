"""
Graph-based GratitudeService that stores all gratitude data as memories in the graph.

This implements the "Graph Memory as Identity Architecture" patent by routing
all gratitude and community metrics through the memory system as TSDBGraphNodes.

"Gratitude is not only the greatest of virtues, but the parent of all others." - Cicero
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from enum import Enum
from uuid import uuid4

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.schemas.community_schemas_v1 import CommunityHealth
from ciris_engine.schemas.graph_schemas_v1 import TSDBGraphNode, GraphScope, GraphNode, NodeType
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryQuery, MemoryOpResult
from ciris_engine.message_buses.memory_bus import MemoryBus

logger = logging.getLogger(__name__)


class GratitudeType(str, Enum):
    """Types of gratitude expressions."""
    THANKS_GIVEN = "thanks_given"
    THANKS_RECEIVED = "thanks_received"
    HELP_ACKNOWLEDGED = "help_acknowledged"
    APPRECIATION = "appreciation"
    RECIPROCAL = "reciprocal"
    COMMUNITY = "community"


class GraphGratitudeService(Service):
    """
    GratitudeService that stores all gratitude data as graph memories.
    
    This service implements the vision where "everything is a memory" by
    converting gratitude events into graph nodes and edges, creating a
    living social ledger of kindness and reciprocity.
    """
    
    def __init__(self, memory_bus: Optional[MemoryBus] = None) -> None:
        super().__init__()
        self._memory_bus = memory_bus
        self._service_registry: Optional[Any] = None
        
        # Cache for recent gratitude metrics
        self._reciprocity_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._community_health_cache: Dict[str, CommunityHealth] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._last_cache_update = datetime.now(timezone.utc)
    
    def set_service_registry(self, registry: Any) -> None:
        """Set the service registry for accessing memory bus."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.message_buses import MemoryBus
                self._memory_bus = MemoryBus(registry)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")
    
    async def record_gratitude(
        self,
        gratitude_type: GratitudeType,
        from_entity: str,
        to_entity: str,
        context: str,
        channel_id: Optional[str] = None,
        community_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Record a gratitude event as nodes and edges in the graph.
        
        Creates:
        1. A gratitude event node (TSDBGraphNode)
        2. Edge from giver to event
        3. Edge from event to receiver
        4. Updates reciprocity metrics in graph
        """
        try:
            if not self._memory_bus:
                logger.error("Memory bus not available for gratitude storage")
                return {"error": "Memory bus not available"}
            
            event_id = f"gratitude_{int(datetime.now(timezone.utc).timestamp())}_{from_entity[:8]}"
            timestamp = datetime.now(timezone.utc)
            
            # Create gratitude event node
            event_node = TSDBGraphNode(
                id=event_id,
                type=NodeType.TSDB_DATA,
                scope=GraphScope.COMMUNITY,  # Gratitude is community data
                timestamp=timestamp,
                data_type="gratitude_event",
                tags={
                    "gratitude_type": gratitude_type.value,
                    "from_entity": from_entity,
                    "to_entity": to_entity,
                    "channel_id": channel_id or "",
                    "community_id": community_id or "default",
                    **(metadata or {})
                },
                retention_policy="raw",
                attributes={
                    "event_id": event_id,
                    "gratitude_type": gratitude_type.value,
                    "from_entity": from_entity,
                    "to_entity": to_entity,
                    "context": context,
                    "channel_id": channel_id,
                    "community_id": community_id,
                    "timestamp": timestamp.isoformat(),
                    "data_type": "gratitude_event",
                    "metadata": metadata or {}
                }
            )
            
            # Store the event node
            if not self._memory_bus:
                return {
                    "success": False,
                    "error": "Memory bus not available",
                    "event_id": event_id
                }
            
            result = await self._memory_bus.memorize(
                node=event_node,
                handler_name="gratitude_service",
                metadata={"gratitude_event": True}
            )
            
            if result.status != MemoryOpStatus.OK:
                logger.error(f"Failed to store gratitude event: {result.error}")
                return {"error": result.error}
            
            # Create or update giver node
            giver_node = GraphNode(
                id=f"entity_{from_entity}",
                type=NodeType.USER,
                scope=GraphScope.COMMUNITY,
                attributes={
                    "entity_id": from_entity,
                    "entity_type": "gratitude_giver",
                    "last_gratitude_given": timestamp.isoformat(),
                    "gratitude_given_count": await self._increment_counter(f"entity_{from_entity}", "gratitude_given_count")
                }
            )
            await self._memory_bus.memorize(giver_node, handler_name="gratitude_service")
            
            # Create or update receiver node
            receiver_node = GraphNode(
                id=f"entity_{to_entity}",
                type=NodeType.USER,
                scope=GraphScope.COMMUNITY,
                attributes={
                    "entity_id": to_entity,
                    "entity_type": "gratitude_receiver",
                    "last_gratitude_received": timestamp.isoformat(),
                    "gratitude_received_count": await self._increment_counter(f"entity_{to_entity}", "gratitude_received_count")
                }
            )
            await self._memory_bus.memorize(receiver_node, handler_name="gratitude_service")
            
            # Update reciprocity metrics
            await self._update_reciprocity_in_graph(from_entity, to_entity)
            
            # Update community health
            if community_id:
                await self._update_community_health_in_graph(community_id, "gratitude")
            
            # Also store as a metric for time-series queries
            if self._memory_bus:
                await self._memory_bus.memorize_metric(
                    metric_name="gratitude_events",
                    value=1.0,
                    tags={
                        "gratitude_type": gratitude_type.value,
                        "community": community_id or "default"
                    },
                    scope="community",
                    handler_name="gratitude_service"
                )
            
            logger.info(
                f"Gratitude recorded in graph: {from_entity} → {to_entity} ({gratitude_type.value}): {context[:50]}..."
            )
            
            return {
                "event_id": event_id,
                "status": "recorded",
                "timestamp": timestamp.isoformat(),
                "gratitude_type": gratitude_type.value,
                "from": from_entity,
                "to": to_entity,
                "context": context
            }
            
        except Exception as e:
            logger.error(f"Failed to record gratitude: {e}")
            return {"error": str(e)}
    
    async def get_gratitude_balance(self, entity_id: str) -> Dict[str, Any]:
        """
        Get the gratitude balance for an entity from the graph.
        """
        try:
            if not self._memory_bus:
                return {"error": "Memory bus not available"}
            
            # Recall entity node
            entity_query = MemoryQuery(
                node_id=f"entity_{entity_id}",
                scope=GraphScope.COMMUNITY,
                type=None,
                include_edges=False,
                depth=1
            )
            
            entity_nodes = await self._memory_bus.recall(
                recall_query=entity_query,
                handler_name="gratitude_service"
            )
            
            if not entity_nodes:
                return {
                    "entity_id": entity_id,
                    "gratitude_given_count": 0,
                    "gratitude_received_count": 0,
                    "balance": 0,
                    "gratitude_ratio": 0.0
                }
            
            entity_node = entity_nodes[0]
            given_count = entity_node.attributes.get("gratitude_given_count", 0)
            received_count = entity_node.attributes.get("gratitude_received_count", 0)
            
            # Query recent gratitude events
            recent_events = await self._memory_bus.recall_timeseries(
                scope="community",
                hours=24 * 7,  # Last week
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="gratitude_service"
            )
            
            # Filter for this entity's events
            given_events = []
            received_events = []
            reciprocity_scores: Dict[str, float] = {}
            
            for event in recent_events:
                tags = event.tags or {}
                if tags.get('from_entity') == entity_id:
                    given_events.append(event)
                    # Track reciprocity
                    to_entity = tags.get('to_entity')
                    if to_entity:
                        reciprocity_scores[to_entity] = reciprocity_scores.get(to_entity, 0) + 1
                        
                elif tags.get('to_entity') == entity_id:
                    received_events.append(event)
                    # Track reciprocity
                    from_entity = tags.get('from_entity')
                    if from_entity:
                        reciprocity_scores[from_entity] = reciprocity_scores.get(from_entity, 0) - 1
            
            # Normalize reciprocity scores
            for other_entity, score in reciprocity_scores.items():
                if score == 0:
                    reciprocity_scores[other_entity] = 1.0  # Perfect reciprocity
                else:
                    reciprocity_scores[other_entity] = 1.0 / (1.0 + abs(score))
            
            return {
                "entity_id": entity_id,
                "gratitude_given_count": given_count,
                "gratitude_received_count": received_count,
                "balance": received_count - given_count,
                "reciprocity_scores": reciprocity_scores,
                "recent_given": given_events[-5:],
                "recent_received": received_events[-5:],
                "gratitude_ratio": received_count / max(1, given_count)
            }
            
        except Exception as e:
            logger.error(f"Failed to get gratitude balance: {e}")
            return {"error": str(e)}
    
    async def get_community_gratitude_metrics(
        self, 
        community_id: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get community-wide gratitude metrics from the graph.
        """
        try:
            if not self._memory_bus:
                return {"error": "Memory bus not available"}
            
            # Query gratitude events from time-series
            events = await self._memory_bus.recall_timeseries(
                scope="community",
                hours=hours,
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="gratitude_service"
            )
            
            # Filter for gratitude events
            gratitude_events = []
            for event in events:
                if event.metric_name == 'gratitude_events':
                    tags = event.tags or {}
                    if community_id is None or tags.get('community') == community_id:
                        gratitude_events.append(event)
            
            # Calculate metrics
            total_gratitude = len(gratitude_events)
            unique_givers = len(set((e.tags or {}).get('from_entity', '') for e in gratitude_events if (e.tags or {}).get('from_entity')))
            unique_receivers = len(set((e.tags or {}).get('to_entity', '') for e in gratitude_events if (e.tags or {}).get('to_entity')))
            
            # Type breakdown
            type_counts: Dict[str, int] = defaultdict(int)
            for event in gratitude_events:
                grat_type = (event.tags or {}).get('gratitude_type')
                if grat_type:
                    type_counts[grat_type] += 1
            
            # Get community health from cache or graph
            health = await self._get_community_health(community_id or "default")
            
            # Calculate reciprocity index
            reciprocity_index = 0.0
            if unique_givers > 0 and unique_receivers > 0:
                reciprocity_index = min(unique_givers, unique_receivers) / max(unique_givers, unique_receivers)
            
            return {
                "community_id": community_id or "default",
                "time_window_hours": hours,
                "total_gratitude_events": total_gratitude,
                "unique_givers": unique_givers,
                "unique_receivers": unique_receivers,
                "gratitude_by_type": dict(type_counts),
                "reciprocity_index": round(reciprocity_index, 3),
                "community_health": {
                    "helpfulness": health.helpfulness,
                    "flourishing": health.flourishing,
                    "activity_level": health.activity_level,
                    "conflict_level": health.conflict_level
                },
                "daily_average": total_gratitude / max(1, hours / 24)
            }
            
        except Exception as e:
            logger.error(f"Failed to get community gratitude metrics: {e}")
            return {"error": str(e)}
    
    async def check_reciprocity(
        self, 
        entity_a: str, 
        entity_b: str
    ) -> Dict[str, Any]:
        """
        Check reciprocity between two entities using graph data.
        """
        try:
            if not self._memory_bus:
                return {"error": "Memory bus not available"}
            
            # Check cache first
            sorted_entities = sorted([entity_a, entity_b])
            cache_key: Tuple[str, str] = (sorted_entities[0], sorted_entities[1])
            if cache_key in self._reciprocity_cache:
                if datetime.now(timezone.utc) - self._last_cache_update < self._cache_ttl:
                    return self._reciprocity_cache[cache_key]
            
            # Query reciprocity node from graph
            reciprocity_query = MemoryQuery(
                node_id=f"reciprocity_{entity_a}_{entity_b}",
                scope=GraphScope.COMMUNITY,
                type=None,
                include_edges=False,
                depth=1
            )
            
            reciprocity_nodes = await self._memory_bus.recall(
                recall_query=reciprocity_query,
                handler_name="gratitude_service"
            )
            
            if reciprocity_nodes:
                node = reciprocity_nodes[0]
                result = {
                    "entity_a": entity_a,
                    "entity_b": entity_b,
                    "a_thanked_b": node.attributes.get("a_to_b_count", 0),
                    "b_thanked_a": node.attributes.get("b_to_a_count", 0),
                    "total_exchanges": node.attributes.get("total_exchanges", 0),
                    "balance": node.attributes.get("balance", 0),
                    "reciprocity_score": node.attributes.get("reciprocity_score", 0.0),
                    "relationship": node.attributes.get("relationship", "no_interaction")
                }
            else:
                # No reciprocity data yet
                result = {
                    "entity_a": entity_a,
                    "entity_b": entity_b,
                    "a_thanked_b": 0,
                    "b_thanked_a": 0,
                    "total_exchanges": 0,
                    "balance": 0,
                    "reciprocity_score": 0.0,
                    "relationship": "no_interaction"
                }
            
            # Update cache
            self._reciprocity_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to check reciprocity: {e}")
            return {"error": str(e)}
    
    async def get_abundance_metrics(self, community_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get post-scarcity abundance metrics from the graph.
        
        In the graph memory architecture, abundance is measured by:
        - The density of gratitude connections
        - The diversity of knowledge being shared
        - The flow of reciprocal appreciation
        """
        try:
            if not self._memory_bus:
                return {"error": "Memory bus not available"}
            
            # Query community metrics from graph
            metrics = await self.get_community_gratitude_metrics(community_id, hours=24 * 30)
            
            # Calculate abundance based on gratitude flow
            total_gratitude = metrics.get("total_gratitude_events", 0)
            unique_participants = metrics.get("unique_givers", 0) + metrics.get("unique_receivers", 0)
            reciprocity_index = metrics.get("reciprocity_index", 0)
            
            # Abundance is generated by gratitude exchanges
            abundance_generated = total_gratitude * reciprocity_index
            
            # Knowledge diversity from gratitude types
            gratitude_types = metrics.get("gratitude_by_type", {})
            knowledge_diversity = len(gratitude_types)
            
            # Connection density
            if unique_participants > 1:
                max_connections = unique_participants * (unique_participants - 1) / 2
                actual_connections = total_gratitude
                connection_density = min(1.0, actual_connections / max_connections)
            else:
                connection_density = 0.0
            
            # Beautiful compassion index
            compassion_index = self._calculate_compassion_index(
                reciprocity_index,
                unique_participants,
                knowledge_diversity
            )
            
            return {
                "community_id": community_id or "default",
                "total_abundance_generated": round(abundance_generated, 2),
                "knowledge_diversity_score": knowledge_diversity,
                "knowledge_domains": list(gratitude_types.keys()),
                "connection_density": round(connection_density, 3),
                "abundance_per_member": round(abundance_generated / max(1, unique_participants), 2),
                "vision_alignment": {
                    "post_scarcity_progress": min(100, int(abundance_generated)),
                    "beautiful_compassion_index": compassion_index,
                    "distributed_knowledge_nodes": total_gratitude
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get abundance metrics: {e}")
            return {"error": str(e)}
    
    async def _increment_counter(self, node_id: str, field: str) -> int:
        """Increment a counter field in a node."""
        try:
            if not self._memory_bus:
                return 0
                
            # Recall node
            query = MemoryQuery(node_id=node_id, scope=GraphScope.COMMUNITY, type=None, include_edges=False, depth=1)
            nodes = await self._memory_bus.recall(query, handler_name="gratitude_service")
            
            if nodes:
                current_value = nodes[0].attributes.get(field, 0)
                # Type assertion - we know this is an int from get(field, 0)
                return int(current_value) + 1
            else:
                return 1
                
        except Exception:
            return 1
    
    async def _update_reciprocity_in_graph(self, from_entity: str, to_entity: str) -> None:
        """Update reciprocity metrics in the graph."""
        try:
            if not self._memory_bus:
                return
                
            # Create sorted pair for consistent node ID
            sorted_pair = sorted([from_entity, to_entity])
            entity_pair: Tuple[str, str] = (sorted_pair[0], sorted_pair[1])
            reciprocity_id = f"reciprocity_{entity_pair[0]}_{entity_pair[1]}"
            
            # Recall existing reciprocity node
            query = MemoryQuery(node_id=reciprocity_id, scope=GraphScope.COMMUNITY, type=None, include_edges=False, depth=1)
            nodes = await self._memory_bus.recall(query, handler_name="gratitude_service")
            
            if nodes:
                node = nodes[0]
                attrs = node.attributes
                
                # Update counts
                if from_entity < to_entity:
                    attrs["a_to_b_count"] = attrs.get("a_to_b_count", 0) + 1
                else:
                    attrs["b_to_a_count"] = attrs.get("b_to_a_count", 0) + 1
            else:
                # Create new reciprocity node
                attrs = {
                    "entity_a": entity_pair[0],
                    "entity_b": entity_pair[1],
                    "a_to_b_count": 1 if from_entity < to_entity else 0,
                    "b_to_a_count": 1 if from_entity > to_entity else 0,
                }
            
            # Calculate metrics
            a_to_b = attrs["a_to_b_count"]
            b_to_a = attrs["b_to_a_count"]
            total = a_to_b + b_to_a
            balance = a_to_b - b_to_a
            
            if total > 0:
                reciprocity_score = 1.0 - (abs(balance) / total)
            else:
                reciprocity_score = 0.0
            
            attrs.update({
                "total_exchanges": total,
                "balance": balance,
                "reciprocity_score": round(reciprocity_score, 3),
                "relationship": self._classify_relationship(reciprocity_score, total),
                "last_updated": datetime.now(timezone.utc).isoformat()
            })
            
            # Store updated node
            reciprocity_node = GraphNode(
                id=reciprocity_id,
                type=NodeType.CONCEPT,
                scope=GraphScope.COMMUNITY,
                attributes=attrs
            )
            
            await self._memory_bus.memorize(reciprocity_node, handler_name="gratitude_service")
            
        except Exception as e:
            logger.error(f"Failed to update reciprocity: {e}")
    
    async def _update_community_health_in_graph(self, community_id: str, event_type: str) -> None:
        """Update community health metrics in the graph."""
        try:
            if not self._memory_bus:
                return
                
            # Recall community health node
            health_id = f"community_health_{community_id}"
            query = MemoryQuery(node_id=health_id, scope=GraphScope.COMMUNITY, type=None, include_edges=False, depth=1)
            nodes = await self._memory_bus.recall(query, handler_name="gratitude_service")
            
            if nodes:
                node = nodes[0]
                health = CommunityHealth(
                    helpfulness=node.attributes.get("helpfulness", 50),
                    flourishing=node.attributes.get("flourishing", 50),
                    activity_level=node.attributes.get("activity_level", 50),
                    conflict_level=node.attributes.get("conflict_level", 10)
                )
            else:
                health = CommunityHealth()
            
            # Update based on event type
            if event_type == "gratitude":
                health.helpfulness = min(100, health.helpfulness + 1)
                health.flourishing = min(100, health.flourishing + 1)
                health.activity_level = min(100, health.activity_level + 1)
            
            # Store updated health
            health_node = GraphNode(
                id=health_id,
                type=NodeType.CONCEPT,
                scope=GraphScope.COMMUNITY,
                attributes={
                    "community_id": community_id,
                    "helpfulness": health.helpfulness,
                    "flourishing": health.flourishing,
                    "activity_level": health.activity_level,
                    "conflict_level": health.conflict_level,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            )
            
            if self._memory_bus:
                await self._memory_bus.memorize(health_node, handler_name="gratitude_service")
            
            # Update cache
            self._community_health_cache[community_id] = health
            
        except Exception as e:
            logger.error(f"Failed to update community health: {e}")
    
    async def _get_community_health(self, community_id: str) -> CommunityHealth:
        """Get community health from cache or graph."""
        # Check cache
        if community_id in self._community_health_cache:
            if datetime.now(timezone.utc) - self._last_cache_update < self._cache_ttl:
                return self._community_health_cache[community_id]
        
        # Query from graph
        try:
            if not self._memory_bus:
                return CommunityHealth()  # Return default
                
            health_id = f"community_health_{community_id}"
            query = MemoryQuery(node_id=health_id, scope=GraphScope.COMMUNITY, type=None, include_edges=False, depth=1)
            nodes = await self._memory_bus.recall(query, handler_name="gratitude_service")
            
            if nodes:
                node = nodes[0]
                health = CommunityHealth(
                    helpfulness=node.attributes.get("helpfulness", 50),
                    flourishing=node.attributes.get("flourishing", 50),
                    activity_level=node.attributes.get("activity_level", 50),
                    conflict_level=node.attributes.get("conflict_level", 10)
                )
            else:
                health = CommunityHealth()
            
            # Update cache
            self._community_health_cache[community_id] = health
            self._last_cache_update = datetime.now(timezone.utc)
            
            return health
            
        except Exception:
            return CommunityHealth()
    
    def _classify_relationship(self, reciprocity_score: float, total_exchanges: int) -> str:
        """Classify a relationship based on reciprocity metrics."""
        if total_exchanges == 0:
            return "no_interaction"
        elif total_exchanges < 3:
            return "new_relationship"
        elif reciprocity_score > 0.8:
            return "balanced_reciprocal"
        elif reciprocity_score > 0.5:
            return "mostly_reciprocal"
        elif reciprocity_score > 0.2:
            return "somewhat_reciprocal"
        else:
            return "one_sided"
    
    def _calculate_compassion_index(
        self, 
        reciprocity_index: float,
        unique_participants: int,
        knowledge_diversity: int
    ) -> float:
        """Calculate the beautiful compassion index."""
        # Normalize factors
        reciprocity_factor = reciprocity_index
        participation_factor = min(1.0, unique_participants / 10)
        diversity_factor = min(1.0, knowledge_diversity / len(GratitudeType))
        
        # Weighted combination
        compassion_index = (
            (reciprocity_factor * 0.4) +
            (participation_factor * 0.3) +
            (diversity_factor * 0.3)
        )
        
        return round(compassion_index * 100, 1)
    
    async def start(self) -> None:
        """Start the gratitude service."""
        logger.info("GraphGratitudeService started - routing all gratitude through memory graph")
    
    async def stop(self) -> None:
        """Stop the gratitude service."""
        logger.info("GraphGratitudeService stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the gratitude service is healthy."""
        return self._memory_bus is not None
    
    def get_service_type(self) -> ServiceType:
        """This is an audit-like service for community metrics."""
        return ServiceType.AUDIT
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        return [
            "record_gratitude", "get_gratitude_balance", "get_community_gratitude_metrics",
            "check_reciprocity", "get_abundance_metrics", "graph_storage"
        ]