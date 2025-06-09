# CIRIS DMA Creation Guide

This guide explains how to create new Decision Making Algorithms (DMAs) in the CIRIS system using the modular interface.

## Overview

DMAs in CIRIS are responsible for evaluating thoughts and making decisions. The system supports four main types of DMAs:

1. **Ethical DMAs** - Evaluate thoughts against ethical principles
2. **Common Sense DMAs (CSDMA)** - Check for plausibility and common sense
3. **Domain-Specific DMAs (DSDMA)** - Apply domain expertise
4. **Action Selection DMAs** - Choose concrete actions from multiple inputs

## Quick Start

### 1. Choose Your DMA Type

Select the appropriate interface based on your DMA's purpose:

```python
from ciris_engine.protocols.dma_interface import (
    EthicalDMAInterface,      # For ethical evaluation
    CSDMAInterface,           # For common sense checking
    DSDMAInterface,           # For domain-specific logic
    ActionSelectionDMAInterface,  # For action selection
)
```

### 2. Create Your DMA Class

```python
from ciris_engine.protocols.dma_interface import EthicalDMAInterface
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext

class MyEthicalDMA(EthicalDMAInterface):
    async def evaluate(
        self, 
        thought_item: ProcessingQueueItem, 
        context: Optional[ThoughtContext] = None,
        **kwargs
    ) -> EthicalDMAResult:
        # Your evaluation logic here
        return EthicalDMAResult(
            alignment_check={"principle": "evaluation"},
            decision="approved",
            rationale="Meets ethical standards"
        )
```

### 3. Add Prompts (Recommended)

Create a YAML file at `ciris_engine/dma/prompts/myethicaldma.yml`:

```yaml
system_header: "You are an ethical evaluator for the CIRIS system..."
evaluation_template: "Evaluate the following thought: {thought_content}"
decision_criteria: "Base your decision on the four CIRIS principles..."
```

### 4. Register Your DMA

Add your DMA to the appropriate registry in `factory.py`:

```python
ETHICAL_DMA_REGISTRY: Dict[str, Type[EthicalDMAInterface]] = {
    "MyEthicalDMA": MyEthicalDMA,
}
```

### 5. Use Your DMA

```python
from ciris_engine.dma.factory import create_dma

# Create your DMA instance
my_dma = await create_dma(
    dma_type="ethical",
    dma_identifier="MyEthicalDMA",
    service_registry=service_registry,
    model_name="gpt-4o",
    prompt_overrides={"custom_prompt": "Custom value"}
)

# Use it
result = await my_dma.evaluate(thought_item, context)
```

## Advanced Features

### Faculty Integration

Add epistemic faculties for enhanced evaluation:

```python
from ciris_engine.protocols.faculties import EpistemicFaculty

class MyAdvancedDMA(ActionSelectionDMAInterface):
    async def evaluate(
        self,
        triaged_inputs: Dict[str, Any],
        enable_recursive_evaluation: bool = False,
        **kwargs
    ) -> ActionSelectionResult:
        # Use faculties for additional insight
        if self.faculties:
            faculty_results = await self.apply_faculties(
                content=str(triaged_inputs["original_thought"].content),
                context=triaged_inputs
            )
            # Integrate faculty results into decision making
            
        # Your evaluation logic here
        return ActionSelectionResult(...)
```

### Recursive Evaluation on Guardrail Failure

For Action Selection DMAs, implement recursive evaluation:

```python
class MyActionSelectionDMA(ActionSelectionDMAInterface):
    async def recursive_evaluate_with_faculties(
        self,
        triaged_inputs: Dict[str, Any],
        guardrail_failure_context: Dict[str, Any]
    ) -> ActionSelectionResult:
        # Apply faculties for deeper analysis
        faculty_results = await self.apply_faculties(
            content=str(triaged_inputs["original_thought"].content),
            context=guardrail_failure_context
        )
        
        # Add faculty insights and re-evaluate
        enhanced_inputs = {
            **triaged_inputs,
            "faculty_evaluations": faculty_results,
            "guardrail_context": guardrail_failure_context
        }
        
        return await self.evaluate(enhanced_inputs, enable_recursive_evaluation=False)
```

## Best Practices

### 1. Prompt Organization

- **Always separate prompts from logic** using YAML files
- Use descriptive prompt keys like `system_header`, `evaluation_template`
- Support prompt overrides for customization
- Include examples and calibration data in prompts

### 2. Error Handling

```python
async def evaluate(self, thought_item: ProcessingQueueItem, **kwargs) -> EthicalDMAResult:
    try:
        # Your evaluation logic
        result = await self._perform_evaluation(thought_item)
        return result
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        # Return fallback result
        return EthicalDMAResult(
            alignment_check={"error": str(e)},
            decision="error",
            rationale=f"Evaluation failed: {e}"
        )
```

### 3. Resource Usage Tracking

```python
from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage

async def evaluate(self, thought_item: ProcessingQueueItem, **kwargs) -> EthicalDMAResult:
    start_time = time.time()
    
    # Your evaluation logic
    result = await self._perform_evaluation(thought_item)
    
    # Add resource usage tracking
    result.resource_usage = ResourceUsage(
        tokens_used=tokens_consumed,
        execution_time_ms=int((time.time() - start_time) * 1000),
        model_used=self.model_name
    )
    
    return result
```

### 4. Type Safety

Always use the correct input/output types for your DMA interface:

```python
# ✅ Good - Type safe
class MyDMA(EthicalDMAInterface):
    async def evaluate(
        self, 
        thought_item: ProcessingQueueItem,  # Correct input type
        context: Optional[ThoughtContext] = None,
        **kwargs
    ) -> EthicalDMAResult:  # Correct output type
        pass

# ❌ Bad - Wrong types
class BadDMA(EthicalDMAInterface):
    async def evaluate(self, data: Dict) -> Dict:  # Wrong types
        pass
```

## Testing Your DMA

Create comprehensive tests for your DMA:

```python
import pytest
from ciris_engine.processor.processing_queue import ProcessingQueueItem

@pytest.mark.asyncio
async def test_my_dma_evaluation():
    # Setup
    thought_item = ProcessingQueueItem(
        thought_id="test-123",
        content="Test thought content"
    )
    
    dma = MyEthicalDMA(service_registry=mock_registry)
    
    # Test
    result = await dma.evaluate(thought_item)
    
    # Assertions
    assert isinstance(result, EthicalDMAResult)
    assert result.decision is not None
    assert result.rationale is not None
```

## Integration Examples

### Example 1: Custom Ethical DMA

```python
class ComplianceDMA(EthicalDMAInterface):
    """DMA for checking regulatory compliance."""
    
    async def evaluate(
        self, 
        thought_item: ProcessingQueueItem, 
        context: Optional[ThoughtContext] = None,
        **kwargs
    ) -> EthicalDMAResult:
        llm_service = await self.get_llm_service()
        
        # Apply compliance checking logic
        prompt = self.prompts["compliance_check_template"].format(
            thought_content=thought_item.content
        )
        
        response = await llm_service.call_llm_structured(
            model=self.model_name,
            response_model=EthicalDMAResult,
            messages=[
                {"role": "system", "content": self.prompts["system_header"]},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response
```

### Example 2: Domain-Specific DMA with Faculties

```python
class HealthcareDSDMA(DSDMAInterface):
    """DMA specialized for healthcare domain decisions."""
    
    async def evaluate(
        self,
        thought_item: ProcessingQueueItem,
        current_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> DSDMAResult:
        # Apply epistemic faculties first
        faculty_insights = await self.apply_faculties(
            content=str(thought_item.content),
            context=current_context
        )
        
        # Incorporate medical domain knowledge
        domain_context = {
            "medical_guidelines": self._get_medical_guidelines(),
            "patient_safety_factors": self._assess_safety_factors(thought_item),
            "faculty_insights": faculty_insights
        }
        
        # Perform domain-specific evaluation
        return await self._evaluate_healthcare_decision(
            thought_item, 
            domain_context
        )
```

This modular approach allows you to create powerful, type-safe DMAs that integrate seamlessly with the CIRIS system while maintaining clean separation of concerns and excellent testability.