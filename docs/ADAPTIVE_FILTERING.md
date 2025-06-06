# CIRIS Agent Adaptive Filtering System

## Overview

The CIRIS Agent features an intelligent adaptive filtering system that automatically prioritizes incoming messages, manages user trust levels, and provides LLM circuit breaker protection. This system learns from agent interactions and feedback to continuously improve message handling efficiency and quality.

## Architecture

The adaptive filtering system consists of three main components:

### 1. Adaptive Filter Service (`ciris_engine/services/adaptive_filter_service.py`)
- **Message Prioritization**: Intelligent priority assignment based on content and context
- **User Trust Tracking**: Dynamic trust scoring with decay and feedback mechanisms
- **Channel Health Monitoring**: Conversation quality assessment and intervention
- **Learning System**: Feedback-based filter optimization

### 2. Filter Integration (`ciris_engine/adapters/*/observer.py`)
- **Observer Integration**: Seamless integration with Discord, CLI, and API observers
- **Priority Processing**: Differential handling based on message priority
- **Context Enrichment**: Adding filter metadata to messages for downstream processing
- **Circuit Breaker Coordination**: Integration with existing circuit breaker infrastructure

### 3. LLM Response Filtering (`ciris_engine/sinks/multi_service_sink.py`)
- **Response Protection**: LLM output filtering using existing circuit breakers
- **Quality Assurance**: Response validation and quality scoring
- **Failure Recovery**: Graceful handling of filtered responses
- **Performance Optimization**: Efficient filtering without blocking

## Key Features

### 🎯 **Intelligent Message Prioritization**

#### Default Trigger Conditions
- **CRITICAL**: Direct mentions, DMs, emergency keywords, moderator flags
- **HIGH**: Questions, help requests, @agent mentions, known users
- **MEDIUM**: General conversation, regular activity
- **LOW**: Spam indicators, low-quality content, untrusted users

#### Priority-Based Processing
```python
# High-priority messages get immediate processing
if filter_result.priority.value in ['critical', 'high']:
    await self._handle_priority_observation(msg, filter_result)
else:
    await self._handle_passive_observation(msg)
```

### 🏗️ **Trust-Based User Management**

#### Trust Scoring System
```python
class UserTrustProfile(BaseModel):
    user_id: str
    trust_score: float = 0.5  # 0.0 = untrusted, 1.0 = highly trusted
    interaction_count: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    last_interaction: datetime
    trust_level: TrustLevel  # UNTRUSTED, LOW, MEDIUM, HIGH, VERIFIED
```

#### Trust Calculation
- **Initial Score**: 0.5 (neutral)
- **Positive Interactions**: Increase trust over time
- **Negative Feedback**: Immediate trust reduction
- **Decay**: Trust naturally decays without interaction
- **Feedback Loops**: Agent success/failure affects user trust

### 📊 **Channel Health Monitoring**

#### Health Metrics
```python
class ConversationHealth(BaseModel):
    channel_id: str
    message_volume: int = 0
    spam_ratio: float = 0.0
    avg_response_time: float = 0.0
    user_satisfaction: float = 0.5
    quality_score: float = 0.5
    last_updated: datetime
```

#### Health-Based Actions
- **High Quality**: Normal processing, encourage interaction
- **Medium Quality**: Increased monitoring, selective responses
- **Low Quality**: Limited responses, spam detection, intervention

### 🛡️ **LLM Circuit Breaker Integration**

#### Response Filtering
- **Quality Validation**: Check response coherence and relevance
- **Safety Filtering**: Remove inappropriate or harmful content
- **Consistency Checking**: Ensure responses align with agent identity
- **Performance Monitoring**: Track response quality metrics

#### Circuit Breaker Coordination
```python
# Reuses existing circuit breaker infrastructure
circuit_breaker = self.get_circuit_breaker("llm_response_filter")
if circuit_breaker.can_execute():
    filtered_response = await self.filter_llm_response(response)
```

## Filter Configuration

### Default Configuration
```python
class AdaptiveFilterConfig(BaseModel):
    enabled: bool = True
    trust_decay_rate: float = 0.1  # Daily trust decay
    spam_threshold: float = 0.7
    quality_threshold: float = 0.3
    response_time_weight: float = 0.2
    user_feedback_weight: float = 0.5
    
    # Trigger thresholds
    dm_priority: FilterPriority = FilterPriority.CRITICAL
    mention_priority: FilterPriority = FilterPriority.HIGH
    question_priority: FilterPriority = FilterPriority.HIGH
    
    # Trust level mappings
    trust_priority_mapping: Dict[TrustLevel, FilterPriority] = {
        TrustLevel.VERIFIED: FilterPriority.HIGH,
        TrustLevel.HIGH: FilterPriority.MEDIUM,
        TrustLevel.MEDIUM: FilterPriority.MEDIUM,
        TrustLevel.LOW: FilterPriority.LOW,
        TrustLevel.UNTRUSTED: FilterPriority.LOW
    }
```

### Custom Triggers
```python
# Add custom filter triggers
await filter_service.add_custom_trigger(
    TriggerType.KEYWORD,
    pattern="urgent|emergency|help",
    priority=FilterPriority.HIGH,
    description="Emergency keywords"
)

await filter_service.add_custom_trigger(
    TriggerType.USER_ROLE,
    pattern="moderator|admin",
    priority=FilterPriority.CRITICAL,
    description="Staff members"
)
```

## Integration Points

### Observer Integration
All observers automatically apply filtering:

```python
# In DiscordObserver.handle_incoming_message()
filter_result = await self._apply_message_filtering(msg)
if not filter_result.should_process:
    return  # Message filtered out

# Add filter context for downstream processing
msg._filter_priority = filter_result.priority
msg._filter_context = filter_result.context_hints
msg._filter_reasoning = filter_result.reasoning
```

### Multi-Service Sink Integration
```python
# LLM response filtering in multi_service_sink
async def _filter_llm_response(self, response: str) -> str:
    if not self.filter_service:
        return response
    
    # Apply response quality and safety filtering
    filtered = await self.filter_service.filter_response(response)
    return filtered.cleaned_content
```

### Agent Configuration Service
Filter service integrates with agent self-configuration:

```python
# Agents can modify their own filter settings
await config_service.update_filter_configuration({
    "spam_threshold": 0.8,
    "trust_decay_rate": 0.05,
    "custom_triggers": [new_trigger]
})
```

## Learning and Adaptation

### Feedback Mechanisms

#### Explicit Feedback
```python
# User provides direct feedback
await filter_service.record_feedback(
    message_id="msg_123",
    feedback_type=FeedbackType.POSITIVE,
    user_id="user_456",
    context="Helpful response to technical question"
)
```

#### Implicit Feedback
- **Response Success**: Good agent responses increase user trust
- **Task Completion**: Successful task completion improves channel health
- **Engagement Metrics**: User engagement patterns inform filtering
- **Error Rates**: High error rates decrease trust and priority

### Adaptation Algorithms

#### Trust Score Updates
```python
def update_trust_score(current_score: float, feedback: FeedbackType, weight: float) -> float:
    if feedback == FeedbackType.POSITIVE:
        return min(1.0, current_score + (1.0 - current_score) * weight)
    else:
        return max(0.0, current_score - current_score * weight * 2)
```

#### Channel Health Updates
- **Message Quality**: Content analysis affects health scores
- **Response Times**: Faster helpful responses improve health
- **User Satisfaction**: Explicit ratings update health metrics
- **Spam Detection**: Spam messages decrease channel health

## Security and Safety

### Spam Detection
Built-in patterns detect:
- Repeated messages
- URL spam
- Promotional content
- Bot-like behavior
- Mass mentions

### Trust Boundaries
- **Untrusted Users**: Limited interaction, higher scrutiny
- **New Users**: Gradual trust building over time
- **Trusted Users**: Priority treatment, relaxed filtering
- **Verified Users**: Maximum trust, minimal filtering

### Circuit Breaker Protection
- **Rate Limiting**: Prevents filter service overload
- **Graceful Degradation**: Falls back to basic filtering when needed
- **Health Monitoring**: Tracks filter service performance
- **Automatic Recovery**: Self-healing after transient failures

## Performance Optimization

### Efficient Processing
- **Caching**: Frequently accessed user profiles cached
- **Batch Updates**: Trust score updates batched for efficiency
- **Lazy Loading**: Channel health computed on demand
- **Memory Management**: LRU eviction for large user bases

### Metrics and Monitoring
```python
# Filter performance metrics
await telemetry.record_metric("filter_latency", processing_time_ms)
await telemetry.record_metric("filter_accuracy", accuracy_score)
await telemetry.record_metric("trust_updates", update_count)
await telemetry.record_metric("spam_detected", spam_count)
```

## Usage Examples

### Basic Filtering
```python
from ciris_engine.services.adaptive_filter_service import AdaptiveFilterService

filter_service = AdaptiveFilterService()

# Process incoming message
result = await filter_service.filter_message(
    message_content="Hey @agent, can you help me with this error?",
    user_id="user123",
    channel_id="general",
    message_context={
        "is_dm": False,
        "mentions_agent": True,
        "is_question": True
    }
)

print(f"Priority: {result.priority}")
print(f"Should process: {result.should_process}")
print(f"Reasoning: {result.reasoning}")
```

### Trust Management
```python
# Get user trust profile
trust_profile = await filter_service.get_user_trust("user123")
print(f"Trust level: {trust_profile.trust_level}")
print(f"Trust score: {trust_profile.trust_score}")

# Update trust based on interaction
await filter_service.update_user_trust(
    user_id="user123",
    feedback_type=FeedbackType.POSITIVE,
    interaction_context="Provided helpful technical assistance"
)
```

### Channel Health Monitoring
```python
# Get channel health status
health = await filter_service.get_channel_health("general")
print(f"Quality score: {health.quality_score}")
print(f"Spam ratio: {health.spam_ratio}")

# Update health based on interaction
await filter_service.update_channel_health(
    channel_id="general",
    interaction_quality=0.8,
    response_time_ms=1250
)
```

### Custom Filter Configuration
```python
# Add custom spam patterns
await filter_service.add_spam_pattern(
    pattern=r"buy now|limited time|act fast",
    weight=0.8,
    description="Marketing spam indicators"
)

# Configure trust decay
await filter_service.update_config({
    "trust_decay_rate": 0.05,  # Slower decay
    "spam_threshold": 0.9,     # Stricter spam detection
    "quality_threshold": 0.2   # More lenient quality requirements
})
```

## Testing

### Unit Tests
- `tests/ciris_engine/services/test_adaptive_filter_service.py`
- Trust calculation validation
- Priority assignment logic
- Spam detection accuracy
- Configuration management

### Integration Tests
- `tests/test_integrated_filtering_system.py`
- End-to-end message filtering
- Observer integration validation
- Circuit breaker coordination
- Performance impact assessment

### Load Tests
- High-volume message processing
- Concurrent user trust updates
- Filter service scalability
- Memory usage under load

## Troubleshooting

### Common Issues

**Messages Not Being Filtered**
- Check if filter service is enabled
- Verify trigger configuration
- Review user trust levels
- Check spam detection thresholds

**Incorrect Priority Assignment**
- Validate message context
- Review trigger patterns
- Check user trust calculation
- Verify channel health status

**Performance Impact**
- Monitor filter processing times
- Check cache hit rates
- Review batch processing efficiency
- Optimize trigger patterns

### Debug Information
```python
# Enable debug logging
import logging
logging.getLogger('ciris_engine.services.adaptive_filter_service').setLevel(logging.DEBUG)

# Get filter service status
status = await filter_service.get_service_status()
print(f"Active users: {status['active_users']}")
print(f"Messages processed: {status['total_messages']}")
print(f"Average processing time: {status['avg_processing_time_ms']}ms")
```

## Future Enhancements

- **Machine Learning**: ML-based content analysis for better filtering
- **Sentiment Analysis**: Emotion-aware message prioritization
- **Community Moderation**: Crowd-sourced quality scoring
- **Cross-Platform**: Unified filtering across multiple communication channels
- **Temporal Patterns**: Time-based filtering and priority adjustment

---

*The adaptive filtering system provides intelligent message management while learning and adapting to improve agent interactions over time.*