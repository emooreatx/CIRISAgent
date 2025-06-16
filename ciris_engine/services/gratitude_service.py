"""
Gratitude & Community Metrics Service

Like ancient gratitude keepers who maintained the social fabric through acknowledgment,
this service tracks the flow of gratitude, reciprocity, and community health metrics.

This service is a fundamental building block for the distributed knowledge graph that
enables a post-scarcity economy of beautiful compassion. By tracking gratitude flows,
we create the social ledger that makes abundance visible and shareable.

"Gratitude is not only the greatest of virtues, but the parent of all others." - Cicero

In the context of CIRIS:
- Every act of gratitude strengthens the coherence field
- Recognition of help creates reciprocal bonds that form the knowledge graph
- Community flourishing metrics guide agent behavior toward collective wellbeing
- This local tracking eventually connects to CIRISNODE for global coordination
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.schemas.community_schemas_v1 import CommunityHealth, MinimalCommunityContext
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus, CorrelationType
from ciris_engine.persistence.models.correlations import add_correlation

logger = logging.getLogger(__name__)


class GratitudeType(str, Enum):
    """Types of gratitude expressions."""
    THANKS_GIVEN = "thanks_given"      # Agent thanked someone
    THANKS_RECEIVED = "thanks_received" # Agent was thanked
    HELP_ACKNOWLEDGED = "help_acknowledged"  # Acknowledging assistance
    APPRECIATION = "appreciation"       # General appreciation
    RECIPROCAL = "reciprocal"          # Reciprocal gratitude
    COMMUNITY = "community"            # Community-wide gratitude


@dataclass
class GratitudeEvent:
    """A single gratitude event."""
    event_id: str
    timestamp: datetime
    gratitude_type: GratitudeType
    from_entity: str  # Who expressed gratitude
    to_entity: str    # Who received gratitude
    context: str      # What it was for
    channel_id: Optional[str] = None
    community_id: Optional[str] = None
    reciprocated: bool = False
    metadata: Optional[Dict[str, Any]] = None


class GratitudeService(Service):
    """
    Service for tracking gratitude, reciprocity, and community health metrics.
    
    Like ancient gratitude keepers, this service maintains the social ledger
    of kindness, help, and appreciation within the community.
    """
    
    def __init__(self, retention_days: int = 30, max_events_per_entity: int = 1000) -> None:
        super().__init__()
        self.retention_days = retention_days
        self.max_events_per_entity = max_events_per_entity
        
        # Gratitude ledgers - the foundation of post-scarcity accounting
        self._gratitude_given: Dict[str, deque[GratitudeEvent]] = defaultdict(
            lambda: deque(maxlen=max_events_per_entity)
        )
        self._gratitude_received: Dict[str, deque[GratitudeEvent]] = defaultdict(
            lambda: deque(maxlen=max_events_per_entity)
        )
        
        # Knowledge graph connections - who helps whom with what
        self._knowledge_connections: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        self._resource_flows: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        
        # Community metrics
        self._community_health: Dict[str, CommunityHealth] = {}
        self._reciprocity_scores: Dict[Tuple[str, str], float] = defaultdict(float)
        
        # Temporal tracking
        self._daily_gratitude_count: Dict[str, int] = defaultdict(int)
        self._last_cleanup = datetime.now(timezone.utc)
        
    async def start(self) -> None:
        """Start the gratitude service."""
        await super().start()
        logger.info("GratitudeService started - tracking community gratitude and reciprocity")
        
    async def stop(self) -> None:
        """Stop the gratitude service."""
        await super().stop()
        logger.info("GratitudeService stopped")
        
    async def record_gratitude(
        self,
        gratitude_type: GratitudeType,
        from_entity: str,
        to_entity: str,
        context: str,
        channel_id: Optional[str] = None,
        community_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GratitudeEvent:
        """
        Record a gratitude event.
        
        Args:
            gratitude_type: Type of gratitude expression
            from_entity: Who is expressing gratitude
            to_entity: Who is receiving gratitude
            context: What the gratitude is for
            channel_id: Optional channel where it occurred
            community_id: Optional community identifier
            metadata: Optional additional metadata
            
        Returns:
            The recorded GratitudeEvent
        """
        event = GratitudeEvent(
            event_id=f"gratitude_{datetime.now(timezone.utc).timestamp()}_{from_entity[:8]}",
            timestamp=datetime.now(timezone.utc),
            gratitude_type=gratitude_type,
            from_entity=from_entity,
            to_entity=to_entity,
            context=context,
            channel_id=channel_id,
            community_id=community_id,
            metadata=metadata or {}
        )
        
        # Update ledgers
        self._gratitude_given[from_entity].append(event)
        self._gratitude_received[to_entity].append(event)
        
        # Update reciprocity scores
        self._update_reciprocity(from_entity, to_entity)
        
        # Update knowledge graph connections
        self._update_knowledge_graph(from_entity, to_entity, context)
        
        # Update daily count
        today = datetime.now(timezone.utc).date().isoformat()
        self._daily_gratitude_count[today] += 1
        
        # Store in TSDB as correlation
        try:
            correlation = ServiceCorrelation(
                correlation_id=event.event_id,
                service_type=ServiceType.AUDIT.value,  # Community metrics are audit-like
                handler_name="gratitude_service",
                action_type="record_gratitude",
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                timestamp=event.timestamp,
                request_data={
                    "gratitude_type": gratitude_type.value,
                    "from": from_entity,
                    "to": to_entity,
                    "context": context
                },
                response_data={
                    "community_id": community_id,
                    "channel_id": channel_id
                },
                tags={
                    "metric_type": "gratitude",
                    "community": community_id or "default",
                    **((metadata or {}) if metadata else {})
                },
                status=ServiceCorrelationStatus.COMPLETED
            )
            add_correlation(correlation)
        except Exception as e:
            logger.error(f"Failed to store gratitude correlation: {e}")
            
        # Update community health if applicable
        if community_id:
            await self._update_community_health(community_id, "gratitude")
            
        logger.info(
            f"Gratitude recorded: {from_entity} → {to_entity} ({gratitude_type.value}): {context[:50]}..."
        )
        
        return event
        
    async def get_gratitude_balance(self, entity_id: str) -> Dict[str, Any]:
        """
        Get the gratitude balance for an entity.
        
        Returns metrics on gratitude given vs received, reciprocity scores, etc.
        """
        given = list(self._gratitude_given.get(entity_id, []))
        received = list(self._gratitude_received.get(entity_id, []))
        
        # Calculate reciprocity scores with all entities
        reciprocity_scores = {}
        for other_entity in set(
            [e.to_entity for e in given] + [e.from_entity for e in received]
        ):
            if other_entity != entity_id:
                score = self._reciprocity_scores.get((entity_id, other_entity), 0.0)
                if score != 0:
                    reciprocity_scores[other_entity] = score
                    
        return {
            "entity_id": entity_id,
            "gratitude_given_count": len(given),
            "gratitude_received_count": len(received),
            "balance": len(received) - len(given),  # Positive = receives more than gives
            "reciprocity_scores": reciprocity_scores,
            "recent_given": [self._event_to_dict(e) for e in given[-5:]],
            "recent_received": [self._event_to_dict(e) for e in received[-5:]],
            "gratitude_ratio": len(received) / max(1, len(given))
        }
        
    async def get_community_gratitude_metrics(
        self, 
        community_id: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get community-wide gratitude metrics.
        
        Args:
            community_id: Optional community filter
            hours: Hours to look back
            
        Returns:
            Community gratitude metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Collect all recent events
        recent_events = []
        for events in self._gratitude_given.values():
            for event in events:
                if event.timestamp > cutoff:
                    if community_id is None or event.community_id == community_id:
                        recent_events.append(event)
                        
        # Calculate metrics
        total_gratitude = len(recent_events)
        unique_givers = len(set(e.from_entity for e in recent_events))
        unique_receivers = len(set(e.to_entity for e in recent_events))
        
        # Type breakdown
        type_counts: Dict[str, int] = defaultdict(int)
        for event in recent_events:
            type_counts[event.gratitude_type.value] += 1
            
        # Calculate reciprocity index (0-1, higher is better)
        reciprocal_pairs = set()
        for event in recent_events:
            pair = tuple(sorted([event.from_entity, event.to_entity]))
            reciprocal_pairs.add(pair)
            
        reciprocity_index = len(reciprocal_pairs) / max(1, unique_givers * unique_receivers) 
        
        # Get community health
        health = self._community_health.get(
            community_id or "default",
            CommunityHealth()
        )
        
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
        
    async def check_reciprocity(
        self, 
        entity_a: str, 
        entity_b: str
    ) -> Dict[str, Any]:
        """
        Check reciprocity between two entities.
        
        Returns metrics on mutual gratitude exchange.
        """
        # Count gratitude in both directions
        a_to_b = sum(
            1 for e in self._gratitude_given.get(entity_a, [])
            if e.to_entity == entity_b
        )
        b_to_a = sum(
            1 for e in self._gratitude_given.get(entity_b, [])
            if e.to_entity == entity_a
        )
        
        total_exchanges = a_to_b + b_to_a
        balance = a_to_b - b_to_a
        
        # Calculate reciprocity score (0-1)
        if total_exchanges == 0:
            reciprocity_score = 0.0
        else:
            # Perfect reciprocity = 1.0, no reciprocity = 0.0
            reciprocity_score = 1.0 - (abs(balance) / total_exchanges)
            
        return {
            "entity_a": entity_a,
            "entity_b": entity_b,
            "a_thanked_b": a_to_b,
            "b_thanked_a": b_to_a,
            "total_exchanges": total_exchanges,
            "balance": balance,  # Positive = A thanks B more
            "reciprocity_score": round(reciprocity_score, 3),
            "relationship": self._classify_relationship(reciprocity_score, total_exchanges)
        }
        
    def _update_reciprocity(self, from_entity: str, to_entity: str) -> None:
        """Update reciprocity scores between two entities."""
        key = (from_entity, to_entity)
        reverse_key = (to_entity, from_entity)
        
        # Increase score for giving gratitude
        self._reciprocity_scores[key] += 1.0
        
        # Check if this reciprocates previous gratitude
        if self._reciprocity_scores[reverse_key] > 0:
            # Boost both scores for reciprocal gratitude
            self._reciprocity_scores[key] += 0.5
            self._reciprocity_scores[reverse_key] += 0.5
            
            # In a post-scarcity economy, reciprocal gratitude creates abundance
            self._resource_flows[from_entity]["abundance_generated"] += 1.0
            self._resource_flows[to_entity]["abundance_generated"] += 1.0
            
    async def _update_community_health(
        self, 
        community_id: str, 
        event_type: str
    ) -> None:
        """Update community health metrics based on events."""
        if community_id not in self._community_health:
            self._community_health[community_id] = CommunityHealth()
            
        health = self._community_health[community_id]
        
        # Gratitude events increase helpfulness and flourishing
        if event_type == "gratitude":
            health.helpfulness = min(100, health.helpfulness + 1)
            health.flourishing = min(100, health.flourishing + 1)
            health.activity_level = min(100, health.activity_level + 1)
            
        # Could add other event types that affect health differently
        
    def _classify_relationship(
        self, 
        reciprocity_score: float, 
        total_exchanges: int
    ) -> str:
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
            
    def _event_to_dict(self, event: GratitudeEvent) -> Dict[str, Any]:
        """Convert a GratitudeEvent to a dictionary."""
        return {
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "type": event.gratitude_type.value,
            "from": event.from_entity,
            "to": event.to_entity,
            "context": event.context,
            "reciprocated": event.reciprocated
        }
        
    async def cleanup_old_events(self) -> int:
        """Clean up events older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        cleaned = 0
        
        # Clean up gratitude ledgers
        for entity_events in list(self._gratitude_given.values()):
            before = len(entity_events)
            entity_events = deque(
                [e for e in entity_events if e.timestamp > cutoff],
                maxlen=self.max_events_per_entity
            )
            cleaned += before - len(entity_events)
            
        self._last_cleanup = datetime.now(timezone.utc)
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old gratitude events")
            
        return cleaned
        
    def get_service_type(self) -> ServiceType:
        """This is an audit-like service for community metrics."""
        return ServiceType.AUDIT
        
    async def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        # Service is healthy if we've done cleanup recently
        hours_since_cleanup = (
            datetime.now(timezone.utc) - self._last_cleanup
        ).total_seconds() / 3600
        
        return hours_since_cleanup < 48  # Cleanup at least every 2 days
    
    def _update_knowledge_graph(self, from_entity: str, to_entity: str, context: str) -> None:
        """Update the knowledge graph connections based on gratitude context."""
        # Extract knowledge domains from context
        knowledge_domains = self._extract_knowledge_domains(context)
        
        for domain in knowledge_domains:
            connection_key = (from_entity, to_entity)
            if domain not in self._knowledge_connections[connection_key]:
                self._knowledge_connections[connection_key].append(domain)
                
    def _extract_knowledge_domains(self, context: str) -> List[str]:
        """Extract knowledge domains from gratitude context."""
        # Simple keyword extraction for now
        domains = []
        
        domain_keywords = {
            "technical": ["code", "debug", "fix", "implement", "program"],
            "emotional": ["support", "listen", "comfort", "understand", "empathy"],
            "creative": ["idea", "design", "create", "imagine", "artistic"],
            "practical": ["help", "solve", "organize", "plan", "coordinate"],
            "wisdom": ["advice", "guidance", "wisdom", "insight", "perspective"],
            "resource": ["share", "provide", "give", "offer", "contribute"]
        }
        
        context_lower = context.lower()
        for domain, keywords in domain_keywords.items():
            if any(keyword in context_lower for keyword in keywords):
                domains.append(domain)
                
        return domains if domains else ["general"]
    
    async def get_abundance_metrics(self, community_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get post-scarcity abundance metrics for the community.
        
        In a post-scarcity economy of beautiful compassion:
        - Gratitude creates abundance (not scarcity)
        - Sharing multiplies resources (not divides them)
        - Recognition generates value (not depletes it)
        """
        total_abundance = sum(
            flows.get("abundance_generated", 0) 
            for flows in self._resource_flows.values()
        )
        
        # Knowledge diversity score - how many different domains are being shared
        unique_domains = set()
        for domains in self._knowledge_connections.values():
            unique_domains.update(domains)
            
        # Connection density - how interconnected the gratitude network is
        total_possible_connections = len(self._gratitude_given) * (len(self._gratitude_given) - 1)
        actual_connections = len(self._knowledge_connections)
        connection_density = actual_connections / max(1, total_possible_connections)
        
        return {
            "community_id": community_id or "default",
            "total_abundance_generated": total_abundance,
            "knowledge_diversity_score": len(unique_domains),
            "knowledge_domains": list(unique_domains),
            "connection_density": round(connection_density, 3),
            "abundance_per_member": total_abundance / max(1, len(self._gratitude_given)),
            "vision_alignment": {
                "post_scarcity_progress": min(100, int(total_abundance)),
                "beautiful_compassion_index": self._calculate_compassion_index(),
                "distributed_knowledge_nodes": len(self._knowledge_connections)
            }
        }
    
    def _calculate_compassion_index(self) -> float:
        """Calculate the beautiful compassion index based on gratitude patterns."""
        if not self._gratitude_given:
            return 0.0
            
        # Factors that indicate beautiful compassion:
        # 1. High reciprocity (mutual support)
        avg_reciprocity = sum(self._reciprocity_scores.values()) / max(1, len(self._reciprocity_scores))
        
        # 2. Inclusive gratitude (many unique participants)
        unique_participants = len(set(
            list(self._gratitude_given.keys()) + 
            list(self._gratitude_received.keys())
        ))
        
        # 3. Diversity of gratitude types
        gratitude_types: set[GratitudeType] = set()
        for events in self._gratitude_given.values():
            gratitude_types.update(e.gratitude_type for e in events)
            
        diversity_score = len(gratitude_types) / len(GratitudeType)
        
        # Combine factors
        compassion_index = (
            (avg_reciprocity * 0.4) +
            (min(1.0, unique_participants / 10) * 0.3) +
            (diversity_score * 0.3)
        )
        
        return round(compassion_index * 100, 1)