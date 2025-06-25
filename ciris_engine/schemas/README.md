# CIRIS Schema Architecture v1

This directory contains the organized, typed schema definitions that replace all `Dict[str, Any]` usage in CIRIS. Every data structure is now properly typed with Pydantic models.

## Schema Categories

### 📋 [Actions](./actions/) - Action Context and Parameters
Schemas for the 10 action types:
- **contexts.py**: Action-specific context (SpeakContext, ToolContext, etc.)
- **parameters.py**: Action-specific parameters (SpeakParameters, ToolParameters, etc.)

### 🧮 [DMA](./dma/) - Decision Making Schemas
Schemas for DMA evaluations and decisions:
- **decisions.py**: DMA results and action selection schemas

### 🎓 [Faculties](./faculties/) - Faculty Assessment Schemas
Schemas for specialized reasoning assessments:
- **assessments.py**: Faculty evaluation results

### 🛡️ [Guardrails](./guardrails/) - Safety Check Schemas
Schemas for guardrail results:
- **results.py**: Guardrail evaluation outcomes

### 🎯 [Handlers](./handlers/) - Handler Operation Schemas
Schemas for handler operations:
- **schemas.py**: Handler context and results

### 🏢 [Services](./services/) - Service Interaction Schemas
Schemas for service calls:
- **metadata.py**: Service call metadata (replaces Dict[str, Any])
- **requests.py**: Typed service requests and responses

### 🧠 [States](./states/) - Cognitive State Schemas
Schemas for agent states:
- **cognitive.py**: The 6 cognitive states and transitions

## Key Schema Replacements

### Before (Dict[str, Any])
```python
# BAD - untyped
metadata: Dict[str, Any] = {
    "service": "memory",
    "method": "recall",
    "correlation_id": str(uuid4())
}
```

### After (Typed Schema)
```python
# GOOD - typed
from ciris_engine.schemas.v1.services import ServiceMetadata

metadata = ServiceMetadata(
    service_name="memory",
    method_name="recall",
    correlation_id=uuid4()
)
```

## Schema Principles

1. **No Dict[str, Any]**: Every dict is now a typed Pydantic model
2. **Validation**: All inputs are validated at the boundary
3. **Serialization**: All schemas support JSON serialization
4. **Evolution**: Schemas are versioned (v1) for future migration
5. **Documentation**: Every field has a description

## Common Patterns

### Optional Fields
```python
class MySchema(BaseModel):
    required_field: str
    optional_field: Optional[str] = None
    with_default: str = "default_value"
```

### Nested Schemas
```python
class ParentSchema(BaseModel):
    child: ChildSchema
    children: List[ChildSchema]
```

### Discriminated Unions
```python
class ActionContext(BaseModel):
    action_type: HandlerActionType
    # Fields vary by action_type
```

## Migration Guide

To migrate from Dict[str, Any]:

1. Identify the dict usage
2. Find or create appropriate schema in v1/
3. Replace dict creation with schema instantiation
4. Update type hints throughout call chain
5. Run mypy to verify

## Adding New Schemas

1. Determine correct category
2. Add schema to appropriate file
3. Update category's __init__.py
4. Add to this README
5. Write schema tests