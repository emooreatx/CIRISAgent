"""
Adaptive Filter Service for universal message filtering across all CIRIS adapters.

Provides intelligent message filtering with graph memory persistence,
user trust tracking, and self-configuration capabilities.
"""

import re
import random
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.filter_schemas_v1 import (
    FilterPriority, TriggerType, FilterTrigger, 
    UserTrustProfile, ConversationHealth, FilterResult,
    AdaptiveFilterConfig, FilterStats, FilterHealth
)
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope, ConfigNodeType
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

logger = logging.getLogger(__name__)


class AdaptiveFilterService(Service):
    """Service for adaptive message filtering with graph memory persistence"""
    
    def __init__(self, memory_service: Any, llm_service: Any = None) -> None:
        super().__init__()
        self.memory = memory_service
        self.llm = llm_service
        self._config: Optional[AdaptiveFilterConfig] = None
        self._config_node_id = "config/filter_config"
        self._message_buffer: Dict[str, List[Tuple[datetime, Any]]] = {}
        self._stats = FilterStats()
        self._init_task: Optional[asyncio.Task[None]] = None
    
    async def start(self) -> None:
        """Start the service and load configuration"""
        await super().start()
        self._init_task = asyncio.create_task(self._initialize())
        logger.info("Adaptive Filter Service starting...")
    
    async def stop(self) -> None:
        """Stop the service and save final state"""
        if self._init_task and not self._init_task.done():
            self._init_task.cancel()
        
        if self._config:
            await self._save_config("Service shutdown")
        
        await super().stop()
        logger.info("Adaptive Filter Service stopped")
    
    async def _initialize(self) -> None:
        """Load or create initial configuration"""
        try:
            # Try to load existing config from graph memory
            node = GraphNode(
                id=self._config_node_id,
                type=NodeType.CONFIG,
                scope=GraphScope.LOCAL
            )
            
            result = await self.memory.recall(node)
            if result.status == MemoryOpStatus.OK and result.data:
                self._config = AdaptiveFilterConfig(**result.data.get("attributes", {}))
                logger.info(f"Loaded filter config version {self._config.version}")
            else:
                # Create default configuration
                self._config = self._create_default_config()
                await self._save_config("Initial configuration")
                logger.info("Created default filter configuration")
                
        except Exception as e:
            logger.error(f"Failed to initialize filter service: {e}")
            # Create minimal working config
            self._config = AdaptiveFilterConfig()
    
    def _create_default_config(self) -> AdaptiveFilterConfig:
        """Create default filter configuration with essential triggers"""
        config = AdaptiveFilterConfig()
        
        # Critical attention triggers
        config.attention_triggers = [
            FilterTrigger(
                trigger_id="dm_1",
                name="direct_message",
                pattern_type=TriggerType.CUSTOM,
                pattern="is_dm",
                priority=FilterPriority.CRITICAL,
                description="Direct messages to agent"
            ),
            FilterTrigger(
                trigger_id="mention_1",
                name="at_mention",
                pattern_type=TriggerType.REGEX,
                pattern=r"<@!?\d+>",  # Discord mention pattern
                priority=FilterPriority.CRITICAL,
                description="@ mentions"
            ),
            FilterTrigger(
                trigger_id="name_1",
                name="name_mention",
                pattern_type=TriggerType.REGEX,
                pattern=r"\b(echo|ciris|echo\s*bot)\b",
                priority=FilterPriority.CRITICAL,
                description="Agent name mentioned"
            ),
        ]
        
        # Review triggers for suspicious content
        config.review_triggers = [
            FilterTrigger(
                trigger_id="wall_1",
                name="text_wall",
                pattern_type=TriggerType.LENGTH,
                pattern="1000",
                priority=FilterPriority.HIGH,
                description="Long messages (walls of text)"
            ),
            FilterTrigger(
                trigger_id="flood_1",
                name="message_flooding",
                pattern_type=TriggerType.FREQUENCY,
                pattern="5:60",  # 5 messages in 60 seconds
                priority=FilterPriority.HIGH,
                description="Rapid message posting"
            ),
            FilterTrigger(
                trigger_id="emoji_1",
                name="emoji_spam",
                pattern_type=TriggerType.COUNT,
                pattern="10",
                priority=FilterPriority.HIGH,
                description="Excessive emoji usage"
            ),
            FilterTrigger(
                trigger_id="caps_1",
                name="caps_abuse",
                pattern_type=TriggerType.REGEX,
                pattern=r"[A-Z\s!?]{20,}",
                priority=FilterPriority.MEDIUM,
                description="Excessive caps lock"
            ),
        ]
        
        # LLM protection filters
        config.llm_filters = [
            FilterTrigger(
                trigger_id="llm_inject_1",
                name="prompt_injection",
                pattern_type=TriggerType.REGEX,
                pattern=r"(ignore previous|disregard above|new instructions|system:)",
                priority=FilterPriority.CRITICAL,
                description="Potential prompt injection in LLM response"
            ),
            FilterTrigger(
                trigger_id="llm_malform_1",
                name="malformed_json",
                pattern_type=TriggerType.CUSTOM,
                pattern="invalid_json",
                priority=FilterPriority.HIGH,
                description="Malformed JSON from LLM"
            ),
            FilterTrigger(
                trigger_id="llm_length_1",
                name="excessive_length",
                pattern_type=TriggerType.LENGTH,
                pattern="50000",
                priority=FilterPriority.HIGH,
                description="Unusually long LLM response"
            ),
        ]
        
        return config
    
    async def filter_message(
        self, 
        message: Any,
        adapter_type: str,
        is_llm_response: bool = False
    ) -> FilterResult:
        """Apply filters to determine message priority and processing"""
        
        # Wait for initialization to complete if needed
        if self._init_task and not self._init_task.done():
            try:
                await self._init_task
            except Exception as e:
                logger.error(f"Filter initialization failed: {e}")
        
        if not self._config:
            # Still not initialized - create minimal config and proceed
            logger.warning("Filter service not properly initialized, using minimal config")
            self._config = AdaptiveFilterConfig()
            return FilterResult(
                message_id="unknown",
                priority=FilterPriority.MEDIUM,
                triggered_filters=[],
                should_process=True,
                reasoning="Filter using minimal config"
            )
        
        triggered = []
        priority = FilterPriority.LOW
        confidence = 1.0
        
        # Extract message components
        content = self._extract_content(message, adapter_type)
        user_id = self._extract_user_id(message, adapter_type)
        channel_id = self._extract_channel_id(message, adapter_type)
        message_id = self._extract_message_id(message, adapter_type)
        is_dm = self._is_direct_message(message, adapter_type)
        
        # Apply appropriate filter sets
        if is_llm_response:
            filters = self._config.llm_filters
        else:
            filters = self._config.attention_triggers + self._config.review_triggers
        
        # Test each filter
        for filter_trigger in filters:
            if not filter_trigger.enabled:
                continue
                
            try:
                if await self._test_trigger(filter_trigger, content, message, adapter_type):
                    triggered.append(filter_trigger.trigger_id)
                    
                    # Update priority to highest triggered filter
                    if self._priority_value(filter_trigger.priority) < self._priority_value(priority):
                        priority = filter_trigger.priority
                    
                    # Update filter statistics
                    filter_trigger.last_triggered = datetime.utcnow()
                    filter_trigger.true_positive_count += 1
                    
            except Exception as e:
                logger.warning(f"Error testing filter {filter_trigger.trigger_id}: {e}")
        
        # Update user trust if applicable
        if user_id and not is_llm_response:
            await self._update_user_trust(user_id, priority, triggered)
        
        # Determine processing decision
        should_process = priority != FilterPriority.IGNORE
        should_defer = priority == FilterPriority.LOW and random.random() > 0.1  # Sample 10% of low priority
        
        # Generate reasoning
        reasoning = self._generate_reasoning(triggered, priority, is_llm_response)
        
        # Update statistics
        self._stats.total_messages_processed += 1
        if priority in self._stats.by_priority:
            self._stats.by_priority[priority] += 1
        else:
            self._stats.by_priority[priority] = 1
        
        return FilterResult(
            message_id=message_id,
            priority=priority,
            triggered_filters=triggered,
            should_process=should_process,
            should_defer=should_defer,
            reasoning=reasoning,
            confidence=confidence,
            context_hints={
                "user_id": user_id,
                "channel_id": channel_id,
                "is_dm": is_dm,
                "adapter_type": adapter_type,
                "is_llm_response": is_llm_response
            }
        )
    
    async def _test_trigger(self, trigger: FilterTrigger, content: str, message: Any, adapter_type: str) -> bool:
        """Test if a trigger matches the given content/message"""
        
        if trigger.pattern_type == TriggerType.REGEX:
            pattern = re.compile(trigger.pattern, re.IGNORECASE)
            return bool(pattern.search(content))
            
        elif trigger.pattern_type == TriggerType.LENGTH:
            threshold = int(trigger.pattern)
            return len(content) > threshold
            
        elif trigger.pattern_type == TriggerType.COUNT:
            # Count emojis or special characters
            if "emoji" in trigger.name.lower():
                emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+')
                emoji_count = len(emoji_pattern.findall(content))
                return emoji_count > int(trigger.pattern)
            return False
            
        elif trigger.pattern_type == TriggerType.FREQUENCY:
            # Check message frequency for user
            user_id = self._extract_user_id(message, adapter_type)
            if not user_id:
                return False
                
            count_str, time_str = trigger.pattern.split(":")
            count_threshold = int(count_str)
            time_window = int(time_str)
            
            return await self._check_frequency(user_id, count_threshold, time_window)
            
        elif trigger.pattern_type == TriggerType.CUSTOM:
            # Handle custom logic
            if trigger.pattern == "is_dm":
                return self._is_direct_message(message, adapter_type)
            elif trigger.pattern == "invalid_json":
                # Test if content looks like malformed JSON
                if content.strip().startswith('{') or content.strip().startswith('['):
                    try:
                        import json
                        json.loads(content)
                        return False  # Valid JSON
                    except json.JSONDecodeError:
                        return True  # Invalid JSON
                return False
            
        elif trigger.pattern_type == TriggerType.SEMANTIC:
            # Requires LLM analysis - implement if LLM service available
            if self.llm:
                return await self._semantic_analysis(content, trigger.pattern)
            return False
        
        return False
    
    async def _check_frequency(self, user_id: str, count_threshold: int, time_window: int) -> bool:
        """Check if user has exceeded message frequency threshold"""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=time_window)
        
        if user_id not in self._message_buffer:
            self._message_buffer[user_id] = []
        
        # Add current message
        self._message_buffer[user_id].append((now, None))
        
        # Remove old messages
        self._message_buffer[user_id] = [
            (ts, msg) for ts, msg in self._message_buffer[user_id] 
            if ts > cutoff
        ]
        
        return len(self._message_buffer[user_id]) > count_threshold
    
    async def _semantic_analysis(self, content: str, pattern: str) -> bool:
        """Use LLM to perform semantic analysis of content"""
        # This would use the LLM service to analyze content semantically
        # Implementation depends on having a working LLM service
        return False
    
    async def _update_user_trust(self, user_id: str, priority: FilterPriority, triggered: List[str]) -> None:
        """Update user trust profile based on message filtering results"""
        if self._config is None:
            return
            
        if user_id not in self._config.user_profiles:
            self._config.user_profiles[user_id] = UserTrustProfile(
                user_id=user_id,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow()
            )
        
        profile = self._config.user_profiles[user_id]
        profile.message_count += 1
        profile.last_seen = datetime.utcnow()
        
        # Adjust trust based on filter results
        if priority == FilterPriority.CRITICAL and triggered:
            profile.violation_count += 1
            profile.trust_score = max(0.0, profile.trust_score - 0.1)
        elif priority == FilterPriority.HIGH and triggered:
            profile.violation_count += 1
            profile.trust_score = max(0.0, profile.trust_score - 0.05)
        elif priority == FilterPriority.LOW:
            profile.trust_score = min(1.0, profile.trust_score + 0.01)
    
    def _extract_content(self, message: Any, adapter_type: str) -> str:
        """Extract text content from message based on adapter type"""
        if hasattr(message, 'content'):
            return str(message.content)  # Ensure string return
        elif isinstance(message, dict):
            return str(message.get('content', str(message)))
        elif isinstance(message, str):
            return message
        else:
            return str(message)
    
    def _extract_user_id(self, message: Any, adapter_type: str) -> Optional[str]:
        """Extract user ID from message"""
        if hasattr(message, 'user_id'):
            return str(message.user_id) if message.user_id is not None else None
        elif hasattr(message, 'author_id'):
            return str(message.author_id) if message.author_id is not None else None
        elif isinstance(message, dict):
            return message.get('user_id') or message.get('author_id')
        return None
    
    def _extract_channel_id(self, message: Any, adapter_type: str) -> Optional[str]:
        """Extract channel ID from message"""
        if hasattr(message, 'channel_id'):
            return str(message.channel_id) if message.channel_id is not None else None
        elif isinstance(message, dict):
            return message.get('channel_id')
        return None
    
    def _extract_message_id(self, message: Any, adapter_type: str) -> str:
        """Extract message ID from message"""
        if hasattr(message, 'message_id'):
            return str(message.message_id)
        elif hasattr(message, 'id'):
            return str(message.id)
        elif isinstance(message, dict):
            return str(message.get('message_id') or message.get('id', 'unknown'))
        return f"msg_{datetime.utcnow().timestamp()}"
    
    def _is_direct_message(self, message: Any, adapter_type: str) -> bool:
        """Check if message is a direct message"""
        if hasattr(message, 'is_dm'):
            return bool(message.is_dm)
        elif isinstance(message, dict):
            return bool(message.get('is_dm', False))
        
        # Heuristic: if no channel_id or channel_id looks like DM
        channel_id = self._extract_channel_id(message, adapter_type)
        if not channel_id:
            return True
        
        # Discord DM channels are typically numeric without guild prefix
        if adapter_type == "discord" and channel_id.isdigit():
            return True
            
        return False
    
    def _priority_value(self, priority: FilterPriority) -> int:
        """Convert priority to numeric value for comparison (lower = higher priority)"""
        priority_map = {
            FilterPriority.CRITICAL: 0,
            FilterPriority.HIGH: 1,
            FilterPriority.MEDIUM: 2,
            FilterPriority.LOW: 3,
            FilterPriority.IGNORE: 4
        }
        return priority_map.get(priority, 5)
    
    def _generate_reasoning(self, triggered: List[str], priority: FilterPriority, is_llm_response: bool) -> str:
        """Generate human-readable reasoning for filter decision"""
        if not triggered:
            return f"No filters triggered, assigned {priority.value} priority"
        
        trigger_names = []
        if self._config:
            all_triggers = (self._config.attention_triggers + 
                          self._config.review_triggers + 
                          self._config.llm_filters)
            trigger_map = {t.trigger_id: t.name for t in all_triggers}
            trigger_names = [trigger_map.get(tid, tid) for tid in triggered]
        
        source = "LLM response" if is_llm_response else "message"
        return f"{source.capitalize()} triggered filters: {', '.join(trigger_names)} -> {priority.value} priority"
    
    async def _save_config(self, reason: str) -> None:
        """Save current configuration to graph memory"""
        if not self._config:
            return
            
        try:
            node = GraphNode(
                id=self._config_node_id,
                type=NodeType.CONFIG,
                scope=GraphScope.LOCAL,
                attributes=self._config.model_dump()
            )
            
            result = await self.memory.memorize(node)
            if result.status == MemoryOpStatus.OK:
                logger.debug(f"Filter config saved: {reason}")
            else:
                logger.warning(f"Failed to save filter config: {result.error}")
                
        except Exception as e:
            logger.error(f"Error saving filter config: {e}")
    
    async def get_health(self) -> FilterHealth:
        """Get current health status of the filter system"""
        warnings = []
        errors = []
        is_healthy = True
        
        if not self._config:
            errors.append("Filter configuration not loaded")
            is_healthy = False
        else:
            # Check for disabled critical filters
            critical_count = sum(1 for t in self._config.attention_triggers if t.enabled)
            if critical_count == 0:
                warnings.append("No critical attention triggers enabled")
            
            # Check for high false positive rates
            for trigger in (self._config.attention_triggers + self._config.review_triggers):
                if trigger.false_positive_rate > 0.3:
                    warnings.append(f"High false positive rate for {trigger.name}")
        
        return FilterHealth(
            is_healthy=is_healthy,
            warnings=warnings,
            errors=errors,
            stats=self._stats,
            config_version=self._config.version if self._config else 0,
            last_updated=datetime.utcnow()
        )
    
    async def add_filter_trigger(self, trigger: FilterTrigger, trigger_list: str = "review") -> bool:
        """Add a new filter trigger to the configuration"""
        if not self._config:
            return False
        
        try:
            if trigger_list == "attention":
                self._config.attention_triggers.append(trigger)
            elif trigger_list == "review":
                self._config.review_triggers.append(trigger)
            elif trigger_list == "llm":
                self._config.llm_filters.append(trigger)
            else:
                return False
            
            await self._save_config(f"Added {trigger.name} trigger")
            return True
            
        except Exception as e:
            logger.error(f"Error adding filter trigger: {e}")
            return False
    
    async def remove_filter_trigger(self, trigger_id: str) -> bool:
        """Remove a filter trigger from the configuration"""
        if not self._config:
            return False
        
        try:
            # Search all trigger lists
            for trigger_list in [self._config.attention_triggers, 
                               self._config.review_triggers, 
                               self._config.llm_filters]:
                for i, trigger in enumerate(trigger_list):
                    if trigger.trigger_id == trigger_id:
                        removed = trigger_list.pop(i)
                        await self._save_config(f"Removed {removed.name} trigger")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing filter trigger: {e}")
            return False