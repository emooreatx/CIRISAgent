"""
Gratitude Tracking Integration for Action Handlers

Automatically detects and records gratitude expressions in agent communications.
"""

import re
import logging
from typing import Optional, Dict, Any, List

from ciris_engine.services.gratitude_service import GratitudeService, GratitudeType
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtType

logger = logging.getLogger(__name__)


class GratitudeTracker:
    """
    Tracks gratitude expressions in agent communications.
    
    Integrates with action handlers to automatically detect and record
    gratitude, appreciation, and acknowledgments.
    """
    
    # Patterns that indicate gratitude
    GRATITUDE_PATTERNS = [
        # Direct thanks
        (r'\b(thank(?:s|ing)?|thx|ty)\b', GratitudeType.THANKS_GIVEN),
        (r'\b(appreciate|appreciation)\b', GratitudeType.APPRECIATION),
        (r'\b(grateful|gratitude)\b', GratitudeType.APPRECIATION),
        
        # Acknowledgments
        (r'\b(acknowledge|acknowledging)\b', GratitudeType.HELP_ACKNOWLEDGED),
        (r'\b(helped me|your help|assistance)\b', GratitudeType.HELP_ACKNOWLEDGED),
        (r'\b(couldn\'t have done|wouldn\'t have)\b', GratitudeType.HELP_ACKNOWLEDGED),
        
        # Reciprocal expressions
        (r'\b(in return|likewise|same to you)\b', GratitudeType.RECIPROCAL),
        (r'\b(mutual|together|team)\b', GratitudeType.COMMUNITY),
    ]
    
    def __init__(self, gratitude_service: Optional[GratitudeService] = None):
        self.gratitude_service = gratitude_service
        self._pattern_cache = [
            (re.compile(pattern, re.IGNORECASE), gtype) 
            for pattern, gtype in self.GRATITUDE_PATTERNS
        ]
        
    async def track_from_thought(
        self,
        thought: Any,
        author_id: str,
        author_name: str,
        channel_id: Optional[str] = None
    ) -> List[str]:
        """
        Track gratitude from a thought object.
        
        Args:
            thought: The thought object to analyze
            author_id: ID of the thought author
            author_name: Name of the thought author
            channel_id: Optional channel ID
            
        Returns:
            List of recorded gratitude event IDs
        """
        if not self.gratitude_service:
            return []
            
        events = []
        
        # Check if this is explicitly a gratitude thought
        if hasattr(thought, 'thought_type') and thought.thought_type == ThoughtType.GRATITUDE:
            event = await self.gratitude_service.record_gratitude(
                gratitude_type=GratitudeType.THANKS_GIVEN,
                from_entity=author_id,
                to_entity="community",  # Generic community gratitude
                context=getattr(thought, 'content', 'Gratitude expression'),
                channel_id=channel_id,
                metadata={
                    "thought_id": getattr(thought, 'thought_id', None),
                    "explicit_gratitude": True
                }
            )
            events.append(event.event_id)
            
        # Also check content for implicit gratitude
        content = getattr(thought, 'content', '')
        if content:
            detected = await self.detect_gratitude_in_text(
                content, author_id, author_name, channel_id
            )
            events.extend([e.event_id for e in detected])
            
        return events
        
    async def track_from_message(
        self,
        message_content: str,
        from_entity: str,
        to_entity: Optional[str] = None,
        channel_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Track gratitude from a message.
        
        Args:
            message_content: The message text
            from_entity: Who sent the message
            to_entity: Who the message was directed to (if known)
            channel_id: Optional channel ID
            metadata: Optional metadata
            
        Returns:
            List of GratitudeEvent objects
        """
        if not self.gratitude_service:
            return []
            
        return await self.detect_gratitude_in_text(
            message_content, 
            from_entity,
            from_entity,  # Use entity ID as name if not provided
            channel_id,
            to_entity,
            metadata
        )
        
    async def detect_gratitude_in_text(
        self,
        text: str,
        from_id: str,
        from_name: str,
        channel_id: Optional[str] = None,
        to_entity: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Detect gratitude expressions in text.
        
        Returns list of recorded GratitudeEvent objects.
        """
        if not self.gratitude_service or not text:
            return []
            
        events = []
        detected_types = set()
        
        # Check each pattern
        for pattern, gratitude_type in self._pattern_cache:
            if pattern.search(text):
                # Avoid duplicate types
                if gratitude_type in detected_types:
                    continue
                    
                detected_types.add(gratitude_type)
                
                # Extract context (surrounding words)
                match = pattern.search(text)
                if match:
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end].strip()
                else:
                    context = text[:100]
                
                # Determine recipient
                recipient = to_entity or self._extract_recipient(text) or "community"
                
                # Record the gratitude
                event = await self.gratitude_service.record_gratitude(
                    gratitude_type=gratitude_type,
                    from_entity=from_id,
                    to_entity=recipient,
                    context=context,
                    channel_id=channel_id,
                    metadata={
                        **(metadata or {}),
                        "from_name": from_name,
                        "detected_pattern": pattern.pattern,
                        "implicit": True
                    }
                )
                events.append(event)
                
        return events
        
    def _extract_recipient(self, text: str) -> Optional[str]:
        """
        Try to extract who is being thanked from the text.
        
        Looks for patterns like "thank you @user" or "thanks John"
        """
        # Look for @mentions
        mention_match = re.search(r'@(\w+)', text)
        if mention_match:
            return mention_match.group(1)
            
        # Look for "thank you/thanks [Name]"
        thanks_match = re.search(
            r'\b(?:thank(?:s|ing)?|appreciate)\s+(?:you\s+)?([A-Z]\w+)\b', 
            text
        )
        if thanks_match and thanks_match.group(1) not in ['You', 'The', 'This', 'That']:
            return thanks_match.group(1)
            
        return None
        
    async def get_gratitude_summary(
        self,
        entity_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get a summary of gratitude for an entity.
        
        Useful for action handlers to understand gratitude context.
        """
        if not self.gratitude_service:
            return {
                "entity_id": entity_id,
                "gratitude_tracking_enabled": False
            }
            
        balance = await self.gratitude_service.get_gratitude_balance(entity_id)
        community_metrics = await self.gratitude_service.get_community_gratitude_metrics(
            hours=hours
        )
        
        return {
            "entity_id": entity_id,
            "gratitude_tracking_enabled": True,
            "personal_balance": {
                "given": balance["gratitude_given_count"],
                "received": balance["gratitude_received_count"],
                "ratio": balance["gratitude_ratio"]
            },
            "community_metrics": {
                "total_gratitude": community_metrics["total_gratitude_events"],
                "reciprocity_index": community_metrics["reciprocity_index"],
                "community_health": community_metrics["community_health"]
            },
            "recent_interactions": balance["recent_given"][:3]
        }