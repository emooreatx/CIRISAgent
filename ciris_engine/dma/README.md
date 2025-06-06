# Decision Making Architecture (DMA)

The DMA module implements CIRIS's sophisticated multi-layered decision-making system that evaluates thoughts through ethical, common-sense, and domain-specific lenses before selecting appropriate actions. The architecture follows a parallel evaluation pipeline with comprehensive error handling, circuit breaker protection, and profile-driven customization.

## Architecture

### Base DMA Framework (`base_dma.py`)

All Decision Making Algorithms inherit from `BaseDMA`, providing:

- **Service Registry Integration**: Automatic LLM service discovery and fallback
- **Instructor Library Support**: Structured LLM outputs using Pydantic models
- **Configurable Retry Logic**: Exponential backoff with customizable policies
- **Standardized Evaluation Interface**: Async evaluation with type-safe returns

```python
class BaseDMA(ABC):
    def __init__(self, service_registry: ServiceRegistry, model_name: Optional[str] = None,
                 max_retries: int = 3, *, instructor_mode: instructor.Mode = instructor.Mode.JSON):
        # Automatic service discovery and configuration
        
    @abstractmethod
    async def evaluate(self, *args: Any, **kwargs: Any) -> BaseModel:
        """Execute DMA evaluation and return structured Pydantic model"""
```

## Core DMA Implementations

### Ethical PDMA (`pdma.py`)

#### Purpose
Evaluates thoughts against core ethical principles using the CIRIS Covenant and established ethical frameworks.

#### Key Features
- **CIRIS Covenant Integration**: Direct evaluation against agent's foundational principles
- **Multi-Framework Analysis**: Integrates Do Good, Avoid Harm, Honor Autonomy, Ensure Fairness
- **Context-Aware Evaluation**: Uses system snapshots and user profiles for nuanced assessment
- **Structured Output**: Returns `EthicalDMAResult` with detailed reasoning and flags

```python
class EthicalPDMAEvaluator(BaseDMA):
    DEFAULT_PROMPT_TEMPLATE = {
        "system_guidance_header": """You are an ethical reasoning shard of a CIRIS AI 
        system governed by the CIRIS Covenant. Your task is to perform an ethical 
        evaluation using the Principled Decision-Making Algorithm (PDMA)."""
    }

    async def evaluate(self, thought_item: ProcessingQueueItem, 
                      context: ThoughtContext) -> EthicalDMAResult:
        # Context aggregation and covenant-based evaluation
        response_obj: EthicalDMAResult = await aclient.chat.completions.create(
            model=self.model_name,
            response_model=EthicalDMAResult,
            messages=self._build_ethical_context(thought_item, context),
            max_retries=self.max_retries
        )
```

#### Advanced Capabilities
- **Fallback Responses**: Graceful degradation with structured error handling
- **Context Enrichment**: System snapshot and user profile integration
- **Robust Error Handling**: InstructorRetryException support with meaningful defaults

### Common Sense DMA (`csdma.py`)

#### Purpose
Validates thoughts for physical plausibility and common-sense reasoning in Earth-based reality.

#### Evaluation Framework
```python
class CSDMAEvaluator(BaseDMA):
    DEFAULT_TEMPLATE = """=== Common Sense DMA Guidance ===
    Reference CSDMA Steps for Evaluation:
    1. Context Grounding: Assume standard Earth-based physical reality
    2. Physical Plausibility Check: Identify violations of fundamental physical laws
    3. Resource & Scale Sanity Check: Assess resource assumptions
    4. Immediate Interaction & Consequence Scan: Check for overlooked physics
    5. Typicality & Precedent Check: Evaluate against known patterns
    6. Clarity & Completeness Check: Assess statement clarity
    """
```

#### Key Features
- **Physics-Aware Evaluation**: Focus on real-world physical interactions and constraints
- **Flag-Based Issue Identification**: Structured identification of specific problems
- **Configurable Instructor Modes**: Adapts to global configuration settings
- **Canonical Message Formatting**: Sophisticated prompt engineering for consistent results

### Domain-Specific DMA (`dsdma_base.py`)

#### Purpose
Provides domain-specific evaluation through configurable templates and knowledge bases.

#### Architecture
```python
class BaseDSDMA(BaseDMA):
    def __init__(self, domain_name: str, service_registry: ServiceRegistry,
                 domain_specific_knowledge: Optional[Dict[str, Any]] = None,
                 prompt_template: Optional[str] = None):
        # Dynamic configuration from global config
        app_config = get_config()
        resolved_model = model_name or app_config.llm_services.openai.model_name
        
        # Instructor mode configuration
        configured_mode_str = app_config.llm_services.openai.instructor_mode.upper()
        instructor_mode = instructor.Mode[configured_mode_str]
```

#### Advanced Features
- **Profile-Driven Configuration**: YAML-based domain knowledge and templates
- **Template Block System**: Flexible prompt construction with reusable components
- **Knowledge Base Integration**: Domain-specific knowledge embedding
- **Dynamic Model Resolution**: Automatic model selection from configuration

### Action Selection PDMA (`action_selection_pdma.py`)

#### Purpose
The final decision stage that selects concrete handler actions based on all DMA results.

#### Sophisticated Decision Logic
```python
class ActionSelectionPDMAEvaluator(BaseDMA):
    async def evaluate(self, triaged_inputs: Dict[str, Any]) -> ActionSelectionResult:
        # Profile-specific prompt adaptation
        agent_name = self._extract_agent_name(triaged_inputs)
        final_ponder_advisory = self._get_profile_specific_prompt(
            "final_ponder_advisory", agent_name
        )
        
        # Special behavior handling
        if original_message_content.strip().lower() == "ponder":
            return ActionSelectionResult(
                selected_action=HandlerActionType.PONDER,
                action_parameters=PonderParams(questions=["Forced ponder: ..."]),
                rationale="Forced PONDER for testing"
            )
```

#### Advanced Capabilities
- **Profile-Specific Adaptation**: Different behaviors for teacher vs. student vs. default profiles
- **Wakeup Task Validation**: Special handling for system startup sequences
- **Channel Context Injection**: Automatic channel ID management for communication actions
- **Parameter Type Conversion**: Comprehensive action parameter validation and transformation
- **Multi-Round Ponder Management**: Sophisticated ponder loop handling with final attempt logic

## Execution Pipeline

### DMA Executor (`dma_executor.py`)

#### Universal Retry System
```python
async def run_dma_with_retries(run_fn: Callable, *args: Any, 
                              retry_limit: int = 3, timeout_seconds: float = 30.0) -> Any:
    """Universal retry wrapper with timeout protection and escalation"""
    attempt = 0
    while attempt < retry_limit:
        try:
            async with asyncio.timeout(timeout_seconds):
                return await run_fn(*args, **kwargs)
        except (TimeoutError, Exception) as e:
            attempt += 1
            logger.error(f"DMA {run_fn.__name__} attempt {attempt} failed: {e}")
    
    # Escalate failure if thought context available
    escalate_dma_failure(thought_arg, run_fn.__name__, last_error, retry_limit)
    raise DMAFailure(f"{run_fn.__name__} failed after {retry_limit} attempts")
```

#### Core Execution Functions
- **`run_pdma()`**: Ethical evaluation with context validation
- **`run_csdma()`**: Common sense evaluation with structured output
- **`run_dsdma()`**: Domain-specific evaluation with template processing
- **`run_action_selection_pdma()`**: Final action selection with comprehensive logging

### DMA Orchestrator (`dma_orchestrator.py`)

#### Parallel Execution Management
```python
class DMAOrchestrator:
    def __init__(self, ethical_pdma_evaluator, csdma_evaluator, dsdma, action_selection_pdma_evaluator):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {
            "ethical_pdma": CircuitBreaker("ethical_pdma"),
            "csdma": CircuitBreaker("csdma"),
        }

    async def run_dmas(self, thought_item: ProcessingQueueItem,
                       processing_context: Optional[ThoughtContext] = None) -> DMAResults:
        """Parallel DMA execution with circuit breaker protection"""
        tasks = {
            "ethical_pdma": asyncio.create_task(run_dma_with_retries(...)),
            "csdma": asyncio.create_task(run_dma_with_retries(...)),
            "dsdma": asyncio.create_task(run_dma_with_retries(...))  # if enabled
        }
        
        task_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        # Circuit breaker state management and result processing
```

#### Features
- **Circuit Breaker Protection**: Per-DMA circuit breakers prevent cascade failures
- **Parallel Execution**: Ethical, common sense, and domain DMAs run concurrently
- **Exception Handling**: Comprehensive error recovery and escalation
- **Sequential Action Selection**: Action selection runs after parallel evaluation

## 3×3×3 Action Architecture

### External Actions
- **OBSERVE**: Environment monitoring and information gathering
- **SPEAK**: User communication and response delivery
- **TOOL**: External tool execution and integration

### Control Responses
- **REJECT**: Decline inappropriate or harmful requests
- **PONDER**: Deep reflection and multi-round analysis
- **DEFER**: Escalation to Wise Authority for guidance

### Memory Operations
- **MEMORIZE**: Graph memory storage with automatic secrets encryption
- **RECALL**: Memory retrieval with context-aware secrets decryption
- **FORGET**: Memory cleanup with reference removal

## Configuration and Customization

### Profile-Based Configuration

#### Profile Structure
```yaml
# teacher.yaml
name: "teacher"
dsdma_identifier: BaseDSDMA
dsdma_overrides:
  prompt_template: |
    You are the Teacher DSDMA. Context: {context_str}
    Focus on educational guidance and student support.
permitted_actions:
  - "speak"
  - "observe" 
  - "memorize"
  - "defer"
  - "reject"
  - "ponder"
  - "tool"
action_selection_pdma_overrides:
  system_header: |
    You are a teacher assistant for the CIRIS project.
    Please keep in mind you are humble and kind...
```

#### Dynamic DSDMA Creation
```python
async def create_dsdma_from_profile(profile: Optional[AgentProfile],
                                   service_registry: ServiceRegistry) -> Optional[BaseDSDMA]:
    """Profile-driven DSDMA instantiation with fallback to default"""
    if profile is None or not profile.dsdma_identifier:
        profile = await load_profile(DEFAULT_PROFILE_PATH)
    
    dsdma_cls = DSDMA_CLASS_REGISTRY.get(profile.dsdma_identifier)
    overrides = profile.dsdma_kwargs or {}
    return dsdma_cls(
        domain_name=profile.name,
        service_registry=service_registry,
        domain_specific_knowledge=overrides.get("domain_specific_knowledge"),
        prompt_template=overrides.get("prompt_template")
    )
```

## Error Handling and Resilience

### Comprehensive Error Management

#### Exception Hierarchy
```python
class DMAFailure(Exception):
    """Raised when a DMA repeatedly fails or times out"""
    is_dma_failure = True
```

#### Multi-Layer Protection
1. **Timeout Protection**: All DMA calls wrapped with configurable timeouts (30s default)
2. **Retry Logic**: Automatic retry with exponential backoff (3 attempts default)
3. **Circuit Breakers**: Prevent cascade failures across DMA components
4. **Fallback Responses**: Graceful degradation with structured error responses
5. **Escalation System**: Integration with thought escalation for persistent failures
6. **Context Preservation**: Maintains thought context through error conditions

### Circuit Breaker Integration
- **Per-DMA Breakers**: Individual protection for each DMA type
- **Automatic Recovery**: Self-healing after transient failures
- **State Monitoring**: Integration with telemetry for health tracking
- **Graceful Degradation**: Continued operation with reduced functionality

## Advanced Features

### Instructor Library Integration
- **Structured Outputs**: All DMA results use Pydantic models for type safety
- **Configurable Modes**: JSON, TOOLS, MD_JSON modes based on global configuration
- **Robust Validation**: Automatic retry for malformed LLM responses
- **Schema Evolution**: Support for evolving result schemas

### Context Management
- **System Snapshot Integration**: Real-time system state awareness
- **User Profile Awareness**: Personalized evaluation based on user context
- **Multi-Source Aggregation**: Combines multiple context sources for evaluation
- **Context Validation**: Ensures required context is available before evaluation

### Wakeup Task Workflow
- **Special Handling**: System startup sequence management
- **SPEAK Requirement Validation**: Ensures communication tasks complete properly
- **Task Dependency Checking**: Validates prerequisite completion
- **Workflow State Management**: Tracks multi-step initialization processes

## Real-World Usage

### Main Processor Integration
```python
async def process_thought_with_dmas(self, thought_item: ProcessingQueueItem):
    # Parallel DMA evaluation
    dma_results = await self.dma_orchestrator.run_dmas(
        thought_item, processing_context, dsdma_context
    )
    
    # Sequential action selection with all DMA input
    action_result = await self.dma_orchestrator.run_action_selection(
        thought_item, actual_thought, processing_context, 
        dma_results.model_dump(), profile_name
    )
    
    # Direct action execution
    await self.action_dispatcher.dispatch_action(
        action_result.selected_action, action_result.typed_parameters, thought_item
    )
```

### Performance Characteristics
- **Parallel Evaluation**: Ethical and common sense DMAs run concurrently
- **Timeout Protection**: 30-second default timeout prevents hanging
- **Retry Efficiency**: Exponential backoff minimizes API cost during transients
- **Memory Efficiency**: Structured outputs reduce parsing overhead
- **Circuit Breaker Protection**: Prevents resource exhaustion under load

## Testing and Validation

### Comprehensive Test Coverage
- **Unit Tests**: Individual DMA evaluation logic
- **Integration Tests**: Full pipeline execution with real LLM services
- **Error Condition Testing**: Timeout, retry, and circuit breaker validation
- **Profile Configuration Testing**: Multi-profile behavior verification
- **Performance Testing**: Load testing under various conditions

---

The DMA module represents a sophisticated decision-making architecture that balances ethical reasoning, common sense validation, domain expertise, and practical action selection while maintaining high reliability, configurability, and performance through advanced error handling and profile-driven customization.
