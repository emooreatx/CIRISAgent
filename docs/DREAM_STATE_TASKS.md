# DREAM State Tasks Reference

This document provides a comprehensive list of all tasks created and executed during the DREAM state, directly from the source code in `dream_processor.py`.

## Overview

The DREAM state runs every 6 hours and creates all tasks immediately upon entry for maximum parallelism. All tasks are processed concurrently using the standard thought/task processing pipeline.

## Complete Task List

### CONSOLIDATING Phase (Memory Operations)

1. **"Consolidate telemetry data from last 6 hours"**
   - Priority: 10
   - Purpose: Consolidates operational metrics into TSDBSummary nodes
   - Reduces storage requirements and improves query performance

2. **"Analyze memory access patterns"**
   - Priority: 9
   - Purpose: Reviews which memories are accessed frequently
   - Helps identify important vs. rarely-used memories

3. **"Compress redundant memories"**
   - Priority: 8
   - Purpose: Identifies and merges duplicate or similar memories
   - Optimizes graph storage efficiency

### ANALYZING Phase (Pattern Recognition)

4. **"Analyze PONDER question themes"**
   - Priority: 10
   - Purpose: Reviews recent PONDER questions for recurring themes
   - Identifies areas of contemplation, uncertainty, or interest

5. **"Process recent incidents for patterns"**
   - Priority: 10
   - Purpose: Analyzes incidents from IncidentManagementService
   - Extracts behavioral adjustments and configuration recommendations

6. **"Detect behavioral patterns in actions"**
   - Priority: 9
   - Purpose: Examines action history for patterns
   - Identifies habits, tendencies, and recurring behaviors

7. **"Process behavioral pattern insights from feedback loop"**
   - Priority: 9
   - Purpose: Retrieves insights from ConfigurationFeedbackLoop
   - Discovers actionable patterns stored as CONCEPT nodes

8. **"Reflect on positive moments and community vibes"**
   - Priority: 7
   - Purpose: Reviews positive_vibe nodes from the community
   - Celebrates good moments and maintains awareness of community energy

### CONFIGURING Phase (Self-Assessment)

9. **"Evaluate current parameter effectiveness"**
   - Priority: 9
   - Purpose: Assesses how well current configuration is working
   - Identifies areas for potential improvement

10. **"Test parameter variations within safety bounds"**
    - Priority: 8
    - Purpose: Explores safe configuration adjustments
    - Tests variations without exceeding 20% variance limit

### PLANNING Phase (Future Work)

11. **"Schedule next dream session"**
    - Priority: 6
    - Purpose: Creates a future memory node for the next dream (6 hours ahead)
    - Ensures regular introspection cycle continues

12. **"Create improvement tasks from insights"**
    - Priority: 6
    - Purpose: Generates actionable tasks based on discovered insights
    - Plans concrete improvements for WORK state

## Conditional Future Tasks

Based on insights discovered during the dream, additional future tasks may be created:

### Identity-Focused Tasks

**"Reflect on core identity and values"**
- Trigger: When identity-focused patterns are detected in insights
- Schedule: 12 hours ahead
- Purpose: Deep reflection on core identity and alignment

### Contemplation-Focused Tasks

**"Address recurring questions through focused analysis"**
- Trigger: When recurring contemplations are identified
- Schedule: 3 hours ahead
- Purpose: Dedicated analysis of persistent questions or concerns

## Implementation Details

### Task Creation
```python
# All tasks created immediately in _create_all_dream_tasks()
self._dream_tasks.extend([
    self.task_manager.create_task(
        description,
        priority=priority,
        context={"channel_id": self.startup_channel_id, "phase": phase}
    )
])
```

### Processing Model
- All tasks activated immediately upon creation
- Processed in parallel through standard thought pipeline
- Each task generates a seed thought for processing
- Results contribute to dream session metrics

### Phase Tracking
The current phase is determined by which tasks are active:
- System monitors active task contexts
- Phase transitions occur naturally as tasks complete
- No explicit phase management required

## Key Differences from Documentation

1. **No Benchmarking**: The current implementation does not include CIRISNode benchmarking tasks
2. **Task-Based Processing**: Everything is a task processed through the standard pipeline
3. **Maximum Parallelism**: All tasks created and activated at once, not sequentially
4. **No Special Dream Logic**: Uses standard task/thought processing, not custom dream methods

## Metrics Tracked

During dream sessions, the following metrics are collected:
- `memories_consolidated`: Count of memories processed
- `patterns_analyzed`: Number of patterns discovered
- `adaptations_made`: Always 0 (no automatic adaptations)
- `future_tasks_scheduled`: Number of future tasks created
- `insights_gained`: List of insights discovered

## Integration Points

1. **IncidentManagementService**: Provides incident analysis
2. **ConfigurationFeedbackLoop**: Provides behavioral pattern insights
3. **MemoryBus**: Used for all RECALL operations
4. **SelfConfigurationService**: Monitors identity variance
5. **TSDBConsolidationService**: Handles telemetry consolidation

---

*This document reflects the actual implementation as of June 2025 and supersedes any conflicting documentation.*