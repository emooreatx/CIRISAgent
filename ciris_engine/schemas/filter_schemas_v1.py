"""
Filter Schemas v1 - Universal message filtering system for CIRIS Agent

Provides adaptive filtering capabilities across all adapters and services
with graph memory persistence and self-configuration support.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Pattern
from datetime import datetime, timezone
from enum import Enum
import re


class FilterPriority(str, Enum):
    """Message priority levels for agent attention"""
    CRITICAL = "critical"      # DMs, @mentions, name mentions
    HIGH = "high"             # New users, suspicious patterns
    MEDIUM = "medium"         # Random sampling, periodic health checks
    LOW = "low"               # Normal traffic
    IGNORE = "ignore"         # Filtered out completely


class TriggerType(str, Enum):
    """Types of filter triggers"""
    REGEX = "regex"           # Regular expression pattern
    COUNT = "count"           # Numeric threshold (e.g., emoji count)
    LENGTH = "length"         # Message length threshold
    FREQUENCY = "frequency"   # Message frequency (count:seconds)
    CUSTOM = "custom"         # Custom logic (e.g., is_dm)
    SEMANTIC = "semantic"     # Meaning-based (requires LLM)


class FilterTrigger(BaseModel):
    """Individual filter trigger definition"""
    trigger_id: str = Field(description="Unique identifier")
    name: str = Field(description="Human-readable name")
    pattern_type: TriggerType
    pattern: str = Field(description="Pattern or threshold value")
    priority: FilterPriority
    description: str
    enabled: bool = True
    
    # Learning metadata
    effectiveness: float = Field(default=0.5, ge=0.0, le=1.0)
    false_positive_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    true_positive_count: int = 0
    false_positive_count: int = 0
    last_triggered: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system")
    
    # For learned patterns
    learned_from: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class UserTrustProfile(BaseModel):
    """Track user behavior for adaptive filtering"""
    user_id: str
    message_count: int = 0
    violation_count: int = 0
    helpful_count: int = 0
    first_seen: datetime
    last_seen: datetime
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    flags: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    
    # Behavioral patterns
    avg_message_length: float = 0.0
    avg_message_interval: float = 0.0  # seconds
    common_triggers: Dict[str, int] = Field(default_factory=dict)


class ConversationHealth(BaseModel):
    """Metrics for conversation health monitoring"""
    channel_id: str
    sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    health_score: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Detailed metrics
    toxicity_level: float = Field(default=0.0, ge=0.0, le=1.0)
    engagement_level: float = Field(default=0.5, ge=0.0, le=1.0)
    topic_coherence: float = Field(default=0.5, ge=0.0, le=1.0)
    user_satisfaction: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Sampling data
    last_sample: Optional[datetime] = None
    samples_today: int = 0
    issues_detected: int = 0


class FilterResult(BaseModel):
    """Result of filtering a message"""
    message_id: str
    priority: FilterPriority
    triggered_filters: List[str]
    should_process: bool
    should_defer: bool = False
    reasoning: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Context for handlers
    suggested_action: Optional[str] = None
    context_hints: Dict[str, Any] = Field(default_factory=dict)


class AdaptiveFilterConfig(BaseModel):
    """Complete filter configuration stored in graph memory"""
    config_id: str = Field(default_factory=lambda: f"filter_config_{datetime.now(timezone.utc).timestamp()}")
    version: int = 1
    
    # Core attention triggers (agent always sees these)
    attention_triggers: List[FilterTrigger] = Field(default_factory=list)
    
    # Suspicious pattern triggers
    review_triggers: List[FilterTrigger] = Field(default_factory=list)
    
    # LLM response filters (protect against malicious LLM)
    llm_filters: List[FilterTrigger] = Field(default_factory=list)
    
    # Channel-specific settings
    channel_configs: Dict[str, ConversationHealth] = Field(default_factory=dict)
    
    # User tracking
    new_user_threshold: int = Field(default=5, description="Messages before user is trusted")
    user_profiles: Dict[str, UserTrustProfile] = Field(default_factory=dict)
    
    # Adaptive learning settings
    auto_adjust: bool = True
    adjustment_interval: int = 3600  # seconds
    effectiveness_threshold: float = 0.3  # Disable filters below this
    false_positive_threshold: float = 0.2  # Review filters above this
    
    # Metadata
    last_adjustment: Optional[datetime] = None
    total_messages_processed: int = 0
    total_issues_caught: int = 0


class FilterStats(BaseModel):
    """Statistics for filter performance monitoring"""
    total_messages_processed: int = 0
    total_filtered: int = 0
    by_priority: Dict[FilterPriority, int] = Field(default_factory=dict)
    by_trigger_type: Dict[TriggerType, int] = Field(default_factory=dict)
    false_positive_reports: int = 0
    true_positive_confirmations: int = 0
    last_reset: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FilterHealth(BaseModel):
    """Overall health metrics for the filtering system"""
    is_healthy: bool = True
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    stats: FilterStats = Field(default_factory=FilterStats)
    config_version: int = 1
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
