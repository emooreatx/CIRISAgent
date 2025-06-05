# Decision Making Architecture (DMA)

The DMA module implements CIRIS's multi-layered decision making system using the 3×3×3 architecture. It provides ethical evaluation, common sense validation, domain-specific assessment, and intelligent action selection.

## Core Components

### DMA Types
- **Ethical DMA** (`csdma.py`): Evaluates actions against ethical frameworks and the agent covenant
- **Common Sense DMA** (`csdma.py`): Validates plausibility and reasonableness of thoughts and actions
- **Domain-Specific DMA** (`dsdma_base.py`): Provides specialized evaluation for specific domains
- **Action Selection PDMA** (`action_selection_pdma.py`): Selects optimal actions from the 3×3×3 action space

### Core Classes
- **Base DMA** (`base_dma.py`): Abstract base class for all DMA implementations
- **PDMA** (`pdma.py`): Probabilistic Decision Making Architecture base
- **DMA Executor** (`dma_executor.py`): Orchestrates DMA pipeline execution
- **DMA Factory** (`factory.py`): Factory pattern for creating DMA instances

## 3×3×3 Action Architecture

### External Actions
- **OBSERVE**: Monitor environment and incoming information
- **SPEAK**: Communicate with users and provide responses  
- **TOOL**: Execute external tools and integrations

### Control Responses  
- **REJECT**: Decline inappropriate or harmful requests
- **PONDER**: Engage in deeper reflection and analysis
- **DEFER**: Escalate to Wise Authority for guidance

### Memory Operations
- **MEMORIZE**: Store important information in graph memory
- **RECALL**: Retrieve information from memory systems
- **FORGET**: Remove outdated or inappropriate information

## DMA Pipeline Flow

1. **Ethical Evaluation**: All thoughts pass through ethical DMA for covenant alignment
2. **Common Sense Check**: Plausibility and reasonableness validation  
3. **Domain Assessment**: Specialized domain-specific evaluation when applicable
4. **Action Selection**: Probabilistic selection of optimal action from 3×3×3 space

## Key Features

- **Multi-Layer Validation**: Every decision passes through multiple evaluation layers
- **Ethical Grounding**: Built-in ethical evaluation using established frameworks
- **Probabilistic Selection**: Advanced probabilistic models for action selection
- **Domain Adaptation**: Specialized DMAs for different knowledge domains
- **Resource Awareness**: Integration with resource monitoring and budgets

## Usage

DMAs are automatically invoked during thought processing:

```python
# DMA pipeline execution
result = await dma_executor.execute_pipeline(
    thought=thought,
    context=context,
    dma_types=['ethical', 'common_sense', 'action_selection']
)

# Action selection specifically  
action_result = await action_selection_pdma.select_action(
    thought=thought,
    context=context
)
```

The DMA system ensures all agent decisions are ethically grounded, contextually appropriate, and aligned with the agent's core values and objectives.
