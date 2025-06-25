# CIRIS Engine Processor Module

The processor module is the core execution engine of CIRISAgent, responsible for orchestrating all thought processing, task management, and state transitions. It implements a sophisticated multi-state processing architecture with specialized processors for different operational modes.

## Architecture Overview

The processor module uses a modular, state-driven architecture where different processors handle specific agent states:

```
AgentProcessor (Main Orchestrator)
├── StateManager (State transitions)
├── WakeupProcessor (WAKEUP state)
├── WorkProcessor (WORK state) 
├── PlayProcessor (PLAY state)
├── SolitudeProcessor (SOLITUDE state)
└── DreamProcessor (DREAM state)
```

Each processor is supported by core management components:
- **ThoughtProcessor**: Core thought processing pipeline
- **ThoughtManager**: Thought generation and lifecycle
- **TaskManager**: Task activation and management
- **ProcessingQueue**: In-memory processing queue
- **DMAOrchestrator**: DMA coordination and execution

## Core Components

### AgentProcessor (`main_processor.py`)

The main orchestrator that coordinates all processing activities and manages state transitions.

**Key Features:**
- Orchestrates specialized processors based on current state
- Manages the main processing loop with configurable rounds
- Handles state transitions between WAKEUP → WORK → PLAY/SOLITUDE/DREAM
- Provides unified status reporting and metrics
- Supports both blocking and non-blocking operation modes

**Key Methods:**
```python
async def start_processing(num_rounds: Optional[int] = None) -> None
async def stop_processing() -> None
def get_status() -> Dict[str, Any]
```

### BaseProcessor (`base_processor.py`)

Abstract base class defining the common interface for all specialized processors.

**Key Features:**
- Standardized processor interface with state support validation
- Common metrics tracking (start_time, items_processed, errors, etc.)
- Shared action dispatch logic
- DMA failure fallback mechanisms (force_ponder, force_defer)
- Thought processing pipeline integration

**Abstract Methods:**
```python
async def can_process(state: AgentState) -> bool
async def process(round_number: int) -> Dict[str, Any]
def get_supported_states() -> List[AgentState]
```

### ThoughtProcessor (`thought_processor.py`)

The core thought processing pipeline that coordinates DMA orchestration, context building, and conscience evaluation.

**Processing Pipeline:**
1. **Fetch Thought**: Retrieve full thought object from persistence
2. **Build Context**: Create comprehensive thought context using ContextBuilder
3. **Run DMAs**: Execute Ethical PDMA, CSDMA, and DSDMA in parallel
4. **Action Selection**: Run ActionSelectionPDMA with DMA results
5. **Apply Conscience**: Continuous ethical evaluation of actions
6. **Handle Special Cases**: Process PONDER, DEFER, and other actions
7. **Update Status**: Persist final action and status

**Key Features:**
- DMA failure handling with automatic fallback to DEFER
- Profile-aware action selection
- Comprehensive error handling and logging
- Telemetry integration for metrics collection
- Conscience-guided retry when ethical concerns arise

### ThoughtManager (`thought_manager.py`)

Manages thought generation, queueing, and processing lifecycle.

**Key Features:**
- **Seed Thought Generation**: Creates initial thoughts for new tasks
- **Queue Management**: Populates and manages processing queue with configurable limits
- **Follow-up Thoughts**: Creates follow-up thoughts from parent thoughts
- **Idle Handling**: Creates monitoring thoughts when no work is available
- **Priority Processing**: Handles memory meta-thoughts with priority

**Key Methods:**
```python
def generate_seed_thought(task: Task, round_number: int) -> Optional[Thought]
def populate_queue(round_number: int) -> int
def create_follow_up_thought(parent_thought: Thought, content: str) -> Optional[Thought]
```

### TaskManager (`task_manager.py`)

Handles task lifecycle operations including activation, prioritization, and completion.

**Key Features:**
- **Task Activation**: Activates pending tasks up to configured limits
- **Wakeup Sequence**: Creates and manages the 5-step wakeup ritual
- **Priority Management**: Handles task prioritization and ordering
- **Cleanup Operations**: Removes old completed tasks

**Wakeup Sequence Steps:**
1. VERIFY_IDENTITY: Core identity affirmation
2. VALIDATE_INTEGRITY: System integrity confirmation  
3. EVALUATE_RESILIENCE: Capability assessment
4. ACCEPT_INCOMPLETENESS: Learning mindset acceptance
5. EXPRESS_GRATITUDE: Ubuntu principle gratitude

### StateManager (`state_manager.py`)

Manages agent state transitions and state-specific behaviors with validation rules.

**Supported States:**
- **SHUTDOWN**: Initial/final state
- **WAKEUP**: Initialization and identity confirmation
- **WORK**: Normal task and thought processing
- **PLAY**: Creative and experimental processing
- **SOLITUDE**: Minimal processing and reflection
- **DREAM**: Idle state with benchmarking and insights

**Key Features:**
- **Transition Validation**: Enforces valid state transitions with optional conditions
- **History Tracking**: Maintains complete state change history
- **Metadata Management**: Tracks state-specific data and metrics
- **Auto-transition Logic**: Handles automatic state changes (e.g., WAKEUP → WORK)

### ProcessingQueue (`processing_queue.py`)

Lightweight in-memory queue for efficient thought processing.

**Key Features:**
- **ProcessingQueueItem**: Optimized representation derived from Thought objects
- **Context Preservation**: Maintains initial context and ponder notes
- **Batch Processing**: Supports batch operations on queue items
- **Memory Efficiency**: Lightweight structure for high-throughput processing

## Specialized Processors

### WakeupProcessor (`wakeup_processor.py`)

Handles the agent's initialization sequence with identity confirmation steps.

**Key Features:**
- **Sequential Steps**: Manages 5-step wakeup ritual execution
- **Non-blocking Mode**: Creates thoughts and returns immediately for async processing
- **Completion Tracking**: Monitors step completion and overall progress
- **Context Building**: Uses ContextBuilder for proper thought context
- **Timeout Management**: Handles step timeouts with graceful failure

**Processing Modes:**
- **Blocking**: Waits for each step completion before proceeding
- **Non-blocking**: Creates thoughts for all steps and returns immediately

### WorkProcessor (`work_processor.py`)

Handles normal task and thought processing with comprehensive workflow management.

**Processing Phases:**
1. **Task Activation**: Activate pending tasks up to limits
2. **Seed Generation**: Create initial thoughts for new tasks  
3. **Queue Population**: Load thoughts into processing queue
4. **Batch Processing**: Process thought batches with fallback handling
5. **Idle Management**: Handle idle states with monitoring thoughts

**Key Features:**
- **Batch Processing**: Efficient concurrent thought processing
- **Error Handling**: Robust error recovery and thought failure management
- **Activity Tracking**: Monitors idle time and activity patterns
- **Metrics Collection**: Comprehensive processing statistics

### PlayProcessor (`play_processor.py`)

Extends WorkProcessor for creative and experimental processing modes.

**Key Features:**
- **Creative Mode**: Enhanced processing for experimental tasks
- **Creativity Metrics**: Tracks creative tasks, experiments, and novel approaches
- **Flexible Processing**: Less constrained processing for exploration
- **Experimentation**: Configurable experimental approach selection

**Enhanced Capabilities:**
- Creative task prioritization
- Experimental prompt variations
- Novel approach exploration
- Learning through creative play

### SolitudeProcessor (`solitude_processor.py`)

Handles minimal processing and reflection during low-activity periods.

**Key Features:**
- **Critical-only Processing**: Only processes high-priority tasks (threshold: 8+)
- **Maintenance Operations**: Performs cleanup of old tasks and thoughts
- **Reflection Activities**: Analyzes patterns and consolidates learning
- **Exit Conditions**: Monitors for conditions requiring return to WORK state

**Processing Focus:**
- Critical task detection and processing
- System maintenance and cleanup
- Pattern analysis and learning reflection  
- Resource conservation during idle periods

### DreamProcessor (`dream_processor.py`)

Manages dream state with benchmark execution and insight generation.

**Key Features:**
- **Benchmark Integration**: Runs HE-300 and simplebench via CIRISNode
- **Pulse System**: Regular "snore" pulses with dream activity
- **Insight Generation**: Periodic analysis of dream patterns
- **Metrics Tracking**: Comprehensive dream session metrics

**Dream Activities:**
- HE-300 topic generation and scoring
- SimpleBench performance evaluation
- Dream insight analysis and reporting
- Snore history maintenance with configurable limits

## Supporting Components

### DMAOrchestrator (`dma_orchestrator.py`)

Coordinates DMA execution with circuit breaker protection and retry logic.

**Key Features:**
- **Parallel Execution**: Runs multiple DMAs concurrently
- **Circuit Breakers**: Protects against repeated DMA failures
- **Retry Logic**: Configurable retry attempts with timeouts
- **Profile Integration**: Profile-aware action selection

**DMA Pipeline:**
1. **Initial DMAs**: Ethical PDMA, CSDMA, DSDMA in parallel
2. **Action Selection**: ActionSelectionPDMA with aggregated results
3. **Error Handling**: Circuit breaker protection and fallback

### ThoughtEscalation (`thought_escalation.py`)

Provides escalation mechanisms for thought processing failures and limits.

**Escalation Types:**
- **Action Limit**: When thoughts exceed action limits
- **SLA Breach**: When processing exceeds time limits
- **Conscience Override**: When conscience evaluation suggests reconsideration
- **DMA Failure**: When DMAs repeatedly fail
- **Max Rounds**: When thoughts exceed round limits

## Key Features

### Non-blocking Processing

The processor module supports non-blocking operation modes that enable:
- Concurrent thought processing without blocking state transitions
- Immediate return from processing calls while work continues asynchronously
- Graceful handling of long-running operations
- Responsive state management and user interaction

### Fallback Mechanisms

Robust fallback handling ensures system resilience:
- **DMA Failures**: Automatic fallback to DEFER actions
- **Processing Errors**: Graceful error recovery with thought failure marking
- **Timeout Handling**: Configurable timeouts with escalation
- **State Recovery**: Automatic recovery from invalid states

### Metrics and Monitoring

Comprehensive metrics collection across all processors:
- **Processing Metrics**: Items processed, errors, round completion times
- **State Metrics**: State durations, transition frequencies
- **Performance Metrics**: Batch processing efficiency, queue utilization
- **Health Metrics**: Circuit breaker status, failure rates

### Configuration Management

Flexible configuration through AppConfig and workflow settings:
- **Processing Limits**: max_active_tasks, max_active_thoughts
- **Timeouts**: DMA timeouts, step completion timeouts
- **Retry Logic**: Retry limits, backoff strategies
- **State Behavior**: Auto-transition rules, idle thresholds

## Usage Patterns

### Basic Processor Initialization

```python
from ciris_engine.processor import AgentProcessor

# Initialize with configuration and dependencies
processor = AgentProcessor(
    app_config=app_config,
    # Profile removed - identity loaded from graph
    thought_processor=thought_processor,
    action_dispatcher=action_dispatcher,
    services=services,
    startup_channel_id=channel_id
)

# Start processing loop
await processor.start_processing(num_rounds=100)
```

### State-specific Processing

```python
# Check processor capabilities
if await work_processor.can_process(AgentState.WORK):
    result = await work_processor.process(round_number=1)
    
# Get processor statistics  
stats = work_processor.get_work_stats()
```

### Custom Processor Implementation

```python
class CustomProcessor(BaseProcessor):
    def get_supported_states(self) -> List[AgentState]:
        return [AgentState.CUSTOM]
    
    async def can_process(self, state: AgentState) -> bool:
        return state == AgentState.CUSTOM
    
    async def process(self, round_number: int) -> Dict[str, Any]:
        # Custom processing logic
        return {"processed": True}
```

## Integration with Other Components

### DMA Integration
- Coordinates with DMA modules for thought evaluation
- Handles DMA failures with appropriate fallbacks
- Supports identity-based DMA configurations (from graph)

### Persistence Integration
- Manages thought and task persistence throughout processing
- Handles status updates and progress tracking
- Supports efficient querying for pending work

### Action Handler Integration
- Dispatches processing results to appropriate action handlers
- Provides context for action execution
- Handles action completion and follow-up

### Conscience Integration
- Applies conscience evaluation to all actions
- Handles conscience-guided retries with specific guidance
- Ensures ethical action selection through epistemic faculties
- Provides insights that flow forward to future decisions

## Performance Considerations

### Batch Processing
The processor module uses batch processing for efficiency:
- Thoughts are processed in configurable batch sizes
- Concurrent processing with asyncio.gather for parallelism
- Circuit breakers prevent cascade failures

### Memory Management
- Lightweight ProcessingQueueItem reduces memory overhead
- Configurable queue limits prevent memory exhaustion
- Automatic cleanup of old completed items

### Scalability
- Modular architecture supports horizontal scaling
- State-based processing enables distributed operation
- Metrics collection supports performance monitoring

## Error Handling

### Graceful Degradation
- Processors continue operating despite individual failures
- Fallback mechanisms ensure forward progress
- Comprehensive error logging for debugging

### Recovery Mechanisms
- Automatic retry logic with exponential backoff
- Circuit breakers protect against repeated failures
- State recovery and validation

## Future Enhancements

### Planned Features
- Dynamic processor loading and configuration
- Enhanced creativity metrics and analysis
- Advanced dream state processing with ML insights
- Distributed processing across multiple nodes

### Extensibility
- Plugin architecture for custom processors
- Configurable processing pipelines
- External integration hooks for monitoring and control

## Debugging and Troubleshooting

### Common Issues
1. **Stuck Processing**: Check for pending thoughts with PROCESSING status
2. **State Transition Failures**: Verify transition rules and conditions
3. **DMA Timeouts**: Adjust timeout settings or check LLM connectivity
4. **Memory Usage**: Monitor queue sizes and processing batch limits

### Diagnostic Tools
- Comprehensive logging with structured metadata
- Processor status and metrics endpoints
- State history tracking for transition analysis
- Performance metrics for bottleneck identification

The processor module represents the heart of CIRISAgent's cognitive architecture, providing a robust, scalable, and extensible foundation for AI agent processing with strong emphasis on ethical operation, system resilience, and principled decision-making.

---

*Copyright © 2025 Eric Moore and CIRIS L3C - Apache 2.0 License*
