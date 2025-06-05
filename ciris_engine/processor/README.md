# Processor

The processor module implements CIRIS's thought processing pipeline and agent state management. It orchestrates the flow from thought generation through DMA evaluation to action execution.

## Core Components

### Main Processor (`main_processor.py`)
Central orchestrator that manages:
- **Agent State Transitions**: SHUTDOWN → WAKEUP → WORK → SOLITUDE → DREAM
- **Processing Rounds**: Batch processing of thoughts with configurable limits
- **Service Coordination**: Integration with all service registries
- **Resource Management**: Memory and processing resource monitoring

### Specialized Processors
- **Wakeup Processor** (`wakeup_processor.py`): Handles agent initialization ritual
- **Work Processor** (`work_processor.py`): Manages active thought processing
- **Solitude Processor** (`solitude_processor.py`): Background maintenance tasks
- **Dream Processor** (`dream_processor.py`): Long-term memory consolidation
- **Play Processor** (`play_processor.py`): Recreational and creative activities

### Supporting Components
- **Thought Manager** (`thought_manager.py`): Thought lifecycle and queue management
- **State Manager** (`state_manager.py`): Agent state transitions and validation
- **Task Manager** (`task_manager.py`): Task creation and dependency management
- **Processing Queue** (`processing_queue.py`): Batched thought processing pipeline
- **Thought Escalation** (`thought_escalation.py`): Priority and urgency handling

## Processing Pipeline

### 1. Thought Generation
- **Seed Thoughts**: Initial thoughts generated from tasks
- **Follow-up Thoughts**: Created by action handlers for continued processing
- **Job Thoughts**: Monitoring and maintenance thoughts

### 2. Queue Management
- **Batching**: Thoughts processed in configurable batch sizes
- **Priority Handling**: Urgent thoughts processed first
- **Resource Limits**: Maximum active thoughts enforced

### 3. DMA Processing
- **Ethical Evaluation**: All thoughts validated against agent covenant
- **Common Sense**: Plausibility and reasonableness checks
- **Action Selection**: Intelligent action selection from 3×3×3 space

### 4. Action Execution
- **Handler Dispatch**: Actions routed to appropriate handlers
- **Follow-up Creation**: Handlers generate follow-up thoughts as needed
- **Completion Tracking**: Task and thought completion management

## Agent States

### SHUTDOWN
- **Purpose**: Safe agent termination
- **Activities**: Resource cleanup, state persistence
- **Transitions**: → WAKEUP (on startup)

### WAKEUP
- **Purpose**: Agent initialization and identity verification
- **Activities**: 5-step wakeup ritual, service initialization
- **Transitions**: → WORK (after successful wakeup)

### WORK
- **Purpose**: Active user interaction and task processing
- **Activities**: User requests, memory operations, tool usage
- **Transitions**: → SOLITUDE (low activity), → DREAM (scheduled)

### SOLITUDE
- **Purpose**: Background maintenance and reflection
- **Activities**: Memory cleanup, system optimization
- **Transitions**: → WORK (new activity), → DREAM (scheduled)

### DREAM
- **Purpose**: Deep processing and memory consolidation
- **Activities**: Long-term memory organization, pattern recognition
- **Transitions**: → WAKEUP (next cycle)

## Key Features

### Resource Management
- **Memory Limits**: Configurable memory usage constraints
- **Processing Quotas**: Thought processing limits per round
- **Service Budgets**: Resource allocation across services

### Fault Tolerance
- **Graceful Degradation**: Continues operation under resource constraints
- **Error Recovery**: Automatic retry and fallback mechanisms
- **State Persistence**: Recoverable agent state across restarts

### Observability
- **Processing Metrics**: Detailed performance and throughput metrics
- **State Tracking**: Complete audit trail of state transitions
- **Debug Capabilities**: Rich debugging and introspection tools

## Usage

### Starting the Processor
```python
from ciris_engine.processor.main_processor import MainProcessor

processor = MainProcessor(
    max_active_thoughts=50,
    processing_timeout=30.0
)

# Start processing with optional round limit
await processor.start_processing(num_rounds=100)
```

### State Management
```python
from ciris_engine.processor.state_manager import AgentState

# Check current state
current_state = processor.state_manager.get_current_state()

# Transition to new state
await processor.state_manager.transition_to(AgentState.WORK)
```

### Processing Configuration
```python
# Configure processing parameters
processor.configure(
    batch_size=10,
    max_rounds=1000,
    resource_limits={
        'memory_mb': 512,
        'tokens_per_round': 10000
    }
)
```

The processor module ensures reliable, efficient, and observable thought processing while maintaining strict adherence to ethical and resource constraints.
