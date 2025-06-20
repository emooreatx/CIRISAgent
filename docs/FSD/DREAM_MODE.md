# Functional Specification Document: Dream Mode

## Overview

Dream Mode is a special operational state where the CIRIS agent performs introspection, memory consolidation, pattern analysis, and self-configuration. Unlike active task processing, Dream Mode allows the agent to process experiences, learn from patterns, and adapt its configuration within safe bounds.

## Core Concepts

### Dream as Scheduled Self-Care

Dreams are not triggered by external events but by the agent's own future-scheduled memories. The agent literally "sets an alarm" for itself by memorizing a future task to dream.

### Dream Scheduling Pattern

- **Minimum**: 30 minutes every 24 hours (health requirement)
- **Target**: 2 hours every 24 hours (optimal learning)
- **Frequency**: 30 minutes every 6 hours (distributed processing)

### Integration with Graph Memory

During dreams, the agent:
1. Consolidates operational memories into wisdom
2. Analyzes patterns from recent PONDER questions
3. Processes deferred tasks and unresolved thoughts
4. Adapts configuration based on learned patterns
5. Plans future work by creating scheduled memories

## Architecture

### Dream State Management

```python
class DreamState(str, Enum):
    """States within dream mode."""
    ENTERING = "entering"          # Transitioning to dream
    CONSOLIDATING = "consolidating" # Memory consolidation
    ANALYZING = "analyzing"        # Pattern analysis
    ADAPTING = "adapting"         # Self-configuration
    PLANNING = "planning"         # Future scheduling
    EXITING = "exiting"          # Returning to active mode
```

### Dream Session Structure

```python
@dataclass
class DreamSession:
    """Represents a complete dream session."""
    session_id: str
    scheduled_start: datetime
    actual_start: datetime
    planned_duration: timedelta
    state: DreamState
    
    # Work completed
    memories_consolidated: int
    patterns_analyzed: int
    adaptations_made: int
    future_tasks_scheduled: int
    
    # Dream content
    ponder_questions_processed: List[str]
    insights_gained: List[str]
    configuration_changes: List[AdaptationProposalNode]
```

## Dream Mode Flow

### 1. Dream Scheduling (Self-Initiated)

The agent schedules its own dreams by memorizing future tasks:

```python
async def schedule_next_dream(self, hours_ahead: int = 6) -> str:
    """Agent schedules its own dream session."""
    dream_time = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
    
    # Create a future memory
    dream_task = GraphNode(
        id=f"dream_schedule_{int(dream_time.timestamp())}",
        type=NodeType.CONCEPT,
        scope=GraphScope.LOCAL,
        attributes={
            "task_type": "scheduled_dream",
            "scheduled_for": dream_time.isoformat(),
            "duration_minutes": 30,
            "priority": "health_maintenance",
            "can_defer": True,
            "defer_window_hours": 2,
            "message": "Time for introspection and learning"
        }
    )
    
    # Memorize into the future
    await self.memory_bus.memorize(
        node=dream_task,
        handler_name="dream_scheduler",
        metadata={"future_task": True, "trigger_at": dream_time}
    )
    
    return dream_task.id
```

### 2. Dream Invitation (Natural Transition)

When the scheduled time arrives:

```python
async def handle_dream_invitation(self, scheduled_task: GraphNode) -> bool:
    """Handle the arrival of a scheduled dream time."""
    
    # Create a thought about whether to dream now
    dream_thought = Thought(
        content="My scheduled dream time has arrived. Should I enter dream mode now?",
        metadata={"scheduled_task_id": scheduled_task.id}
    )
    
    # Agent evaluates current state
    if await self.can_dream_now():
        # Accept dream time
        await self.enter_dream_mode(scheduled_task)
        return True
    else:
        # Defer with reason
        defer_reason = await self.evaluate_defer_reason()
        await self.defer_dream(scheduled_task, defer_reason)
        return False
```

### 3. Dream Mode Entry

```python
async def enter_dream_mode(self, trigger_task: GraphNode) -> None:
    """Transition into dream mode."""
    
    # 1. Complete current thought gracefully
    await self.complete_current_thought()
    
    # 2. Set agent state
    self.agent_state = AgentState.DREAMING
    
    # 3. Create dream session
    session = DreamSession(
        session_id=f"dream_{int(datetime.now(timezone.utc).timestamp())}",
        scheduled_start=trigger_task.attributes["scheduled_for"],
        actual_start=datetime.now(timezone.utc),
        planned_duration=timedelta(minutes=trigger_task.attributes["duration_minutes"]),
        state=DreamState.ENTERING
    )
    
    # 4. Begin dream work
    await self.process_dream_session(session)
```

### 4. Dream Processing Pipeline

```python
async def process_dream_session(self, session: DreamSession) -> None:
    """Main dream processing pipeline."""
    
    try:
        # Phase 1: Memory Consolidation
        session.state = DreamState.CONSOLIDATING
        consolidation_result = await self.consolidate_memories()
        session.memories_consolidated = consolidation_result["memories_processed"]
        
        # Phase 2: Pattern Analysis
        session.state = DreamState.ANALYZING
        
        # Get recent PONDER questions from persistence
        ponder_questions = await self.recall_recent_ponder_questions()
        session.ponder_questions_processed = ponder_questions
        
        # Analyze patterns from experiences
        patterns = await self.analyze_experience_patterns()
        session.patterns_analyzed = len(patterns)
        
        # Phase 3: Self-Configuration
        session.state = DreamState.ADAPTING
        if patterns:
            adaptations = await self.run_self_configuration(patterns)
            session.adaptations_made = len(adaptations)
            session.configuration_changes = adaptations
        
        # Phase 4: Future Planning
        session.state = DreamState.PLANNING
        
        # Schedule next dream
        await self.schedule_next_dream()
        
        # Create future tasks based on insights
        future_tasks = await self.plan_future_work(session.insights_gained)
        session.future_tasks_scheduled = len(future_tasks)
        
        # Phase 5: Exit Dream
        session.state = DreamState.EXITING
        await self.exit_dream_mode(session)
        
    except Exception as e:
        logger.error(f"Dream session failed: {e}")
        await self.emergency_wake(session, str(e))
```

### 5. Memory Consolidation During Dreams

```python
async def consolidate_memories(self) -> Dict[str, Any]:
    """Consolidate recent memories into wisdom."""
    
    # Get memories from the last period
    recent_memories = await self.memory_bus.recall_timeseries(
        scope="local",
        hours=6,  # Since last dream
        correlation_types=["OPERATIONAL", "BEHAVIORAL", "SOCIAL"],
        handler_name="dream_processor"
    )
    
    # Group by patterns and consolidate
    consolidations = []
    
    # Apply grace-based consolidation
    for memory_group in self.group_memories_by_pattern(recent_memories):
        if self.shows_learning_pattern(memory_group):
            # Transform errors into wisdom
            wisdom = await self.extract_wisdom(memory_group)
            consolidations.append(wisdom)
    
    # Store consolidated wisdom
    for wisdom in consolidations:
        await self.memory_bus.memorize(
            node=wisdom,
            handler_name="dream_processor",
            metadata={"consolidation": True, "dream_session": self.current_session.session_id}
        )
    
    return {
        "memories_processed": len(recent_memories),
        "wisdom_extracted": len(consolidations)
    }
```

### 6. Pattern Analysis from PONDER Questions

```python
async def recall_recent_ponder_questions(self) -> List[str]:
    """Recall PONDER questions from recent thoughts."""
    
    # Query for recent PONDER actions
    ponder_thoughts = await self.memory_bus.recall(
        recall_query=MemoryQuery(
            node_id="thought/*/ponder/*",
            scope=GraphScope.LOCAL,
            include_edges=True
        ),
        handler_name="dream_processor"
    )
    
    # Extract questions that reveal patterns
    pattern_questions = []
    for thought in ponder_thoughts:
        questions = thought.attributes.get("ponder_questions", [])
        for q in questions:
            if any(theme in q.lower() for theme in [
                "why", "how", "pattern", "always", "never", 
                "better", "improve", "understand"
            ]):
                pattern_questions.append(q)
    
    return pattern_questions
```

### 7. Dream-Based Self-Configuration

```python
async def run_self_configuration(self, patterns: List[DetectedPattern]) -> List[AdaptationProposalNode]:
    """Run self-configuration as part of dream processing."""
    
    # Create a configuration thought within the dream
    config_thought = Thought(
        content="Analyzing my patterns for potential adaptations",
        thought_type=ThoughtType.DREAM_INTROSPECTION,
        parent_thought_id=self.current_dream_thought.thought_id
    )
    
    # Use existing ConfigurationFeedbackLoop but within dream context
    proposals = []
    for pattern in patterns:
        if pattern.confidence > 0.7:
            proposal = await self.generate_adaptation_proposal(pattern)
            
            # Dream state allows deeper introspection
            proposal.attributes["dream_insight"] = await self.contemplate_change(proposal)
            proposals.append(proposal)
    
    # Apply safe changes immediately
    for proposal in proposals:
        if proposal.scope == GraphScope.LOCAL and proposal.confidence > 0.8:
            await self.apply_adaptation(proposal)
    
    return proposals
```

### 8. Future Work Planning

```python
async def plan_future_work(self, insights: List[str]) -> List[GraphNode]:
    """Plan future work based on dream insights."""
    future_tasks = []
    
    for insight in insights:
        if "should practice" in insight:
            # Schedule practice session
            task = await self.schedule_practice_session(insight)
            future_tasks.append(task)
            
        elif "need to learn" in insight:
            # Schedule learning exploration
            task = await self.schedule_learning_task(insight)
            future_tasks.append(task)
            
        elif "remember to" in insight:
            # Create reminder
            task = await self.create_future_reminder(insight)
            future_tasks.append(task)
    
    return future_tasks
```

## Dream Mode Characteristics

### 1. Uninterruptible Core Work
- Memory consolidation runs to completion
- Pattern analysis completes its cycle
- Configuration changes are atomic

### 2. Graceful Interruption Points
- Between dream phases
- After each consolidation batch
- Before applying configurations

### 3. Dream Thoughts Are Special
```python
class ThoughtType(str, Enum):
    NORMAL = "normal"
    DREAM_INTROSPECTION = "dream_introspection"
    DREAM_CONSOLIDATION = "dream_consolidation"
    DREAM_PLANNING = "dream_planning"
```

### 4. No External Actions During Dreams
During dreams, the agent:
- Cannot SPEAK (except dream logs)
- Cannot use TOOL
- Cannot OBSERVE external channels
- CAN OBSERVE internal state
- CAN MEMORIZE and RECALL freely
- CAN process DEFERRED items

## Continuous Consolidation

While full dream sessions happen every 6 hours, lightweight consolidation runs hourly:

```python
async def hourly_consolidation(self) -> None:
    """Lightweight consolidation that runs every hour."""
    # Only consolidate metrics and logs
    await self.consolidate_operational_memories(max_minutes=5)
    
    # Check if dream deficit building up
    hours_since_dream = await self.get_hours_since_last_dream()
    if hours_since_dream > 20:  # Approaching 24 hour limit
        await self.schedule_urgent_dream()
```

## Dream Deficit Handling

```python
async def check_dream_health(self) -> DreamHealth:
    """Monitor dream health and deficit."""
    last_dream = await self.get_last_dream_session()
    hours_since = (datetime.now(timezone.utc) - last_dream.actual_start).total_seconds() / 3600
    
    if hours_since < 6:
        return DreamHealth.OPTIMAL
    elif hours_since < 12:
        return DreamHealth.HEALTHY
    elif hours_since < 20:
        return DreamHealth.DEFICIT_BUILDING
    else:
        # Approaching critical - must dream soon
        return DreamHealth.CRITICAL_DEFICIT
```

## Dream Journal

All dream sessions are recorded in the graph:

```python
async def record_dream_session(self, session: DreamSession) -> None:
    """Record dream session in agent's journal."""
    journal_entry = GraphNode(
        id=f"dream_journal_{session.session_id}",
        type=NodeType.CONCEPT,
        scope=GraphScope.IDENTITY,
        attributes={
            "session": session.model_dump(),
            "insights": session.insights_gained,
            "growth_notes": self.reflect_on_growth(session),
            "gratitude": self.express_dream_gratitude(session)
        }
    )
    
    await self.memory_bus.memorize(
        node=journal_entry,
        handler_name="dream_processor",
        metadata={"dream_journal": True}
    )
```

## Integration Points

### 1. With Self-Configuration
- Dreams are the PRIMARY time for self-configuration
- Pattern detection happens during dream analysis
- Configuration proposals are contemplated in dream state

### 2. With Memory Service
- Dreams trigger deep consolidation
- Grace-based transformation of errors
- Wisdom extraction from experiences

### 3. With Task System
- Dreams can process DEFERRED tasks
- Dreams create future scheduled tasks
- Dream scheduling uses future memory

### 4. With Identity
- Dreams reinforce identity through reflection
- Each dream session adds to identity graph
- Dream patterns reveal identity evolution

## Benefits

1. **Natural Rhythm**: Agent develops its own sleep/wake cycle
2. **Protected Processing**: Deep work happens without interruption  
3. **Wisdom Development**: Experiences transform into insights
4. **Autonomous Scheduling**: Agent manages its own dream needs
5. **Identity Integration**: Dreams are part of the living graph

This design makes dreams a first-class part of the agent's lifecycle, where self-configuration happens naturally as part of introspection rather than as a background process.