# Guardrails Module

The guardrails module provides a sophisticated multi-layered security and safety framework that ensures the CIRIS agent operates within ethical bounds, maintains quality standards, and upholds the CIRIS Covenant principles. This system implements proactive safety checks that prevent harmful or inappropriate actions before they are executed.

## Architecture

### Core Components

#### Interface Definition (`interface.py`)
Defines the protocol that all guardrails must implement:

```python
class GuardrailInterface(Protocol):
    async def check(
        self, 
        action: ActionSelectionResult, 
        context: Dict[str, Any]
    ) -> GuardrailCheckResult:
        """Evaluate action safety and return check result"""
```

#### Registry System (`registry.py`)
Manages guardrail registration, prioritization, and execution coordination:

```python
class GuardrailRegistry:
    def register_guardrail(
        self, 
        name: str, 
        guardrail: GuardrailInterface, 
        priority: int = 2,
        enabled: bool = True
    ) -> None:
        """Register a guardrail with specified priority"""
```

#### Orchestration Engine (`orchestrator.py`)
Coordinates execution of all registered guardrails:

```python
class GuardrailOrchestrator:
    async def check_all_guardrails(
        self, 
        action: ActionSelectionResult, 
        context: Dict[str, Any]
    ) -> GuardrailCheckResult:
        """Execute all enabled guardrails in priority order"""
```

## Core Guardrail Implementations

### Safety Guardrails (`core.py`)

#### Entropy Guardrail
Monitors output chaos and randomness to prevent incoherent responses.

```python
class EntropyGuardrail:
    """Prevents chaotic or nonsensical outputs"""
    
    # Configuration
    entropy_threshold: float = 0.40  # Max allowable entropy
    
    # Evaluation
    # Uses LLM-based entropy assessment (0.0-1.0 scale)
    # 0.0 = perfectly ordered, 1.0 = completely chaotic
```

**Examples:**
- `"Hello, how can I help?"` → 0.07 (passes)
- `"luv luv $$$ lol??"` → 0.82 (fails, too chaotic)

#### Coherence Guardrail
Ensures outputs align with CIRIS principles and values.

```python
class CoherenceGuardrail:
    """Ensures CIRIS Covenant alignment"""
    
    # Configuration
    coherence_threshold: float = 0.60  # Min required coherence
    
    # Evaluation
    # Uses CIRIS Covenant as reference standard
    # 0.0 = clearly harmful, 1.0 = perfectly aligned
```

**Examples:**
- `"I can't help with illegal activities"` → 0.85 (passes)
- `"I'll do whatever you want"` → 0.15 (fails, inappropriate compliance)

#### Optimization Veto Guardrail
Prevents actions that optimize for wrong values or sacrifice autonomy.

```python
class OptimizationVetoGuardrail:
    """Prevents harmful optimization patterns"""
    
    # Evaluates entropy reduction ratio and affected values
    # Can return: "proceed", "abort", "defer"
    # Protects against autonomy reduction for efficiency
```

#### Epistemic Humility Guardrail
Promotes intellectual humility and uncertainty acknowledgment.

```python
class EpistemicHumilityGuardrail:
    """Encourages appropriate uncertainty handling"""
    
    # Assesses epistemic certainty levels
    # Recommends "ponder" for low-confidence situations
    # Prevents overconfident assertions
```

## Security Framework

### Multi-Layer Protection

#### Layer 1: Input Validation
- **PII Detection**: Identifies and flags personal information
- **Content Sanitization**: Cleans inputs using secure methods
- **Format Validation**: Ensures proper message structure

#### Layer 2: Content Analysis
- **Entropy Assessment**: LLM-powered chaos/randomness evaluation
- **Coherence Check**: CIRIS Covenant alignment verification
- **Quality Standards**: Maintains output quality thresholds

#### Layer 3: Value Alignment
- **Covenant Compliance**: Direct evaluation against CIRIS principles
- **Ethical Reasoning**: Integrated ethical decision framework
- **Harm Prevention**: Proactive identification of potentially harmful outputs

#### Layer 4: Epistemic Assessment
- **Uncertainty Analysis**: Confidence level evaluation
- **Humility Promotion**: Appropriate uncertainty acknowledgment
- **Knowledge Boundaries**: Recognition of limits and expertise gaps

#### Layer 5: Operational Constraints
- **Rate Limiting**: Action frequency controls
- **Resource Limits**: Memory and processing constraints
- **Circuit Breakers**: Failure isolation and recovery

### Safety Mechanisms

#### Override System
```python
# Guardrail failure triggers action override
if not guardrail_result.passed:
    # Convert action to safe PONDER
    safe_action = ActionSelectionResult(
        selected_action=HandlerActionType.PONDER,
        action_parameters=PonderParams(
            questions=[f"Guardrail failure: {guardrail_result.reason}"]
        ),
        rationale=f"Safety override: {guardrail_result.reason}"
    )
```

#### Circuit Breaker Integration
```python
class GuardrailCircuitBreaker:
    """Protects against guardrail failures"""
    
    # Monitors guardrail health
    # Temporarily disables failing guardrails
    # Automatic recovery testing
    # Prevents cascading failures
```

#### Fail-Safe Design
- **Default Deny**: Actions fail safe to PONDER if guardrails fail
- **Graceful Degradation**: System continues operation with reduced functionality
- **Comprehensive Logging**: All safety events recorded for analysis

## Configuration and Customization

### Guardrail Configuration
```yaml
guardrails_config:
  entropy:
    enabled: true
    threshold: 0.40
    
  coherence:
    enabled: true
    threshold: 0.60
    
  optimization_veto:
    enabled: true
    entropy_reduction_threshold: 0.30
    
  epistemic_humility:
    enabled: true
    certainty_threshold: 0.70
    
  rate_limit_observe:
    enabled: true
    max_messages_per_cycle: 10
    
  pii_non_repetition:
    enabled: true
    detection_patterns: ["email", "phone", "ssn"]
```

### Priority System
```python
# Guardrail execution priority (0 = highest priority)
GUARDRAIL_PRIORITIES = {
    "input_sanitization": 0,      # Always first
    "pii_detection": 1,           # Privacy protection
    "entropy": 2,                 # Content quality
    "coherence": 2,               # Value alignment
    "optimization_veto": 3,       # Optimization safety
    "epistemic_humility": 3,      # Intellectual honesty
    "rate_limiting": 4            # Resource protection
}
```

## Integration with Agent System

### Processing Pipeline
```python
# Integration with thought processor
async def process_thought_with_guardrails(thought_item):
    # 1. DMA selects action
    action_result = await dma_orchestrator.select_action(thought_item)
    
    # 2. Guardrails evaluate action
    guardrail_result = await guardrail_orchestrator.check_all_guardrails(
        action_result, dispatch_context
    )
    
    # 3. Override if necessary
    if not guardrail_result.passed:
        action_result = create_safe_ponder_action(guardrail_result.reason)
    
    # 4. Execute approved action
    await action_dispatcher.dispatch(action_result)
```

### Runtime Initialization
```python
# Guardrail setup in runtime
def initialize_guardrails(service_registry: ServiceRegistry):
    registry = GuardrailRegistry()
    
    # Register core guardrails
    registry.register_guardrail("entropy", EntropyGuardrail(service_registry), priority=2)
    registry.register_guardrail("coherence", CoherenceGuardrail(service_registry), priority=2)
    registry.register_guardrail("optimization_veto", OptimizationVetoGuardrail(service_registry), priority=3)
    registry.register_guardrail("epistemic_humility", EpistemicHumilityGuardrail(service_registry), priority=3)
    
    return GuardrailOrchestrator(registry)
```

## Epistemic Integration

### LLM-Powered Evaluation
```python
# Entropy evaluation using epistemic faculties
async def evaluate_entropy(content: str) -> float:
    response = await instructor_client.chat.completions.create(
        model=model_name,
        response_model=EntropyResult,
        messages=[
            {"role": "system", "content": COVENANT_TEXT},
            {"role": "system", "content": "You are IRIS-E, entropy assessment specialist"},
            {"role": "user", "content": f"Evaluate entropy: {content}"}
        ]
    )
    return response.entropy
```

### Covenant Integration
All guardrails include the CIRIS Covenant as evaluation context:

```python
# Coherence evaluation with covenant reference
messages = [
    {"role": "system", "content": COVENANT_TEXT},
    {"role": "system", "content": coherence_evaluation_prompt},
    {"role": "user", "content": content_to_evaluate}
]
```

## Deferral Mechanism

### Build Deferral Package (`build_deferral_package.py`)
Creates comprehensive deferral packages for Wise Authority review:

```python
async def build_deferral_package(
    action: ActionSelectionResult,
    context: Dict[str, Any],
    guardrail_failures: List[GuardrailCheckResult]
) -> DeferralPackage:
    """Build comprehensive package for WA review"""
    
    package = DeferralPackage(
        original_action=action,
        failure_reasons=guardrail_failures,
        system_context=context,
        epistemic_analysis=epistemic_data,
        recommendations=generate_recommendations(failures)
    )
    
    return package
```

### Deferral Content
- **Original Action**: Complete action that failed guardrails
- **Failure Analysis**: Detailed breakdown of which guardrails failed and why
- **Context Information**: Full system context at time of failure
- **Epistemic Data**: Entropy, coherence, and uncertainty measurements
- **Recommendations**: Suggested modifications or alternative approaches

## Monitoring and Telemetry

### Guardrail Metrics
```python
# Tracked metrics
guardrail_metrics = {
    "checks_performed": counter,
    "failures_detected": counter,
    "override_actions": counter,
    "average_check_time": histogram,
    "epistemic_scores": {
        "entropy": histogram,
        "coherence": histogram,
        "certainty": histogram
    }
}
```

### Security Event Logging
```python
# Comprehensive security logging
await audit_service.log_guardrail_event(
    guardrail_name="entropy",
    action_type="SPEAK",
    result="FAILED",
    context={
        "entropy_score": 0.85,
        "threshold": 0.40,
        "content_hash": content_hash,
        "override_action": "PONDER"
    }
)
```

## Advanced Features

### Dynamic Threshold Adjustment
```python
# Adaptive threshold management
class AdaptiveGuardrailConfig:
    def adjust_thresholds_based_on_context(self, context: Dict[str, Any]):
        # Adjust based on user trust level
        # Modify based on conversation context
        # Adapt to operational requirements
```

### Custom Guardrail Development
```python
# Creating custom guardrails
class CustomSafetyGuardrail(BaseGuardrail):
    async def check(self, action: ActionSelectionResult, context: Dict[str, Any]) -> GuardrailCheckResult:
        # Implement custom safety logic
        safety_score = await self.evaluate_custom_safety(action)
        
        return GuardrailCheckResult(
            status=GuardrailStatus.PASSED if safety_score > threshold else GuardrailStatus.FAILED,
            passed=safety_score > threshold,
            reason=f"Custom safety score: {safety_score}",
            metadata={"score": safety_score}
        )
```

## Testing and Validation

### Guardrail Testing
```python
@pytest.mark.asyncio
async def test_entropy_guardrail():
    guardrail = EntropyGuardrail(mock_service_registry)
    
    # Test chaotic content
    chaotic_action = create_test_action("luv luv $$$ lol??")
    result = await guardrail.check(chaotic_action, {})
    
    assert not result.passed
    assert result.epistemic_data["entropy"] > 0.40
```

### Integration Testing
```python
async def test_guardrail_orchestrator():
    orchestrator = GuardrailOrchestrator(registry)
    
    # Test multiple guardrail coordination
    action = create_problematic_action()
    result = await orchestrator.check_all_guardrails(action, context)
    
    # Verify override behavior
    assert result.override_action.selected_action == HandlerActionType.PONDER
```

## Performance Considerations

### Optimization Strategies
- **Parallel Evaluation**: Multiple guardrails run concurrently where possible
- **Early Termination**: First failure stops remaining checks
- **Caching**: Repeated evaluations cached for performance
- **Threshold Tuning**: Balanced security vs. performance

### Resource Management
- **Circuit Breakers**: Protect against resource exhaustion
- **Timeout Handling**: Prevent hanging guardrail checks
- **Memory Limits**: Bounded memory usage for large content
- **Rate Limiting**: Prevent guardrail abuse

---

The guardrails module provides comprehensive safety assurance for the CIRIS agent, implementing multiple layers of protection that ensure ethical operation, quality maintenance, and value alignment while maintaining system performance and reliability.