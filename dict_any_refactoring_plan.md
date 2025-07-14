# Dict[str, Any] Refactoring Plan

## Overview
Total: 412 occurrences of Dict[str, Any] across 125 files

## Parallel Agent Work Assignment

### Agent 1: Core Graph Services (31 occurrences)
**Priority: HIGH**
Files to refactor:
- `ciris_engine/schemas/services/graph/consolidation.py` (14 occurrences)
- `ciris_engine/schemas/services/graph/telemetry.py` (2 occurrences)
- `ciris_engine/schemas/services/graph/memory.py` (1 occurrence)
- `ciris_engine/schemas/services/graph/incident.py` (1 occurrence)
- `ciris_engine/schemas/services/graph/audit.py` (1 occurrence)
- `ciris_engine/schemas/services/graph/attributes.py` (2 occurrences)
- `ciris_engine/logic/services/graph/tsdb_consolidation/` (multiple files)

### Agent 2: SDK Resources (60+ occurrences)
**Priority: HIGH**
Files to refactor:
- `ciris_sdk/resources/telemetry.py` (22 occurrences)
- `ciris_sdk/models.py` (12 occurrences)
- `ciris_sdk/resources/agent.py` (8 occurrences)
- `ciris_sdk/resources/memory.py` (8 occurrences)
- `ciris_sdk/resources/wa.py` (7 occurrences)
- `ciris_sdk/resources/jobs.py` (5 occurrences)
- Other SDK files

### Agent 3: Discord Adapter (36 occurrences)
**Priority: MEDIUM**
Files to refactor:
- `ciris_engine/logic/adapters/discord/discord_embed_formatter.py` (8 occurrences)
- `ciris_engine/logic/adapters/discord/discord_adapter.py` (7 occurrences)
- `ciris_engine/logic/adapters/discord/discord_error_handler.py` (6 occurrences)
- `ciris_engine/logic/adapters/discord/discord_thread_manager.py` (6 occurrences)
- Other Discord adapter files

### Agent 4: API Routes (22 occurrences)
**Priority: MEDIUM**
Files to refactor:
- `ciris_engine/logic/adapters/api/routes/telemetry.py` (5 occurrences)
- `ciris_engine/logic/adapters/api/routes/system_extensions.py` (4 occurrences)
- `ciris_engine/logic/adapters/api/routes/auth.py` (2 occurrences)
- `ciris_engine/logic/adapters/api/routes/users.py` (2 occurrences)
- Other API route files

### Agent 5: Schemas and Models (40+ occurrences)
**Priority: HIGH**
Files to refactor:
- `ciris_engine/schemas/processors/state.py` (5 occurrences)
- `ciris_engine/schemas/processors/base.py` (4 occurrences)
- `ciris_engine/schemas/config/agent.py` (4 occurrences)
- `ciris_engine/schemas/runtime/system_context.py` (5 occurrences)
- Other schema files

### Agent 6: DMA and Action Selection (20+ occurrences)
**Priority: HIGH**
Files to refactor:
- `ciris_engine/logic/dma/action_selection/faculty_integration.py` (6 occurrences)
- `ciris_engine/logic/dma/action_selection_pdma.py` (5 occurrences)
- `ciris_engine/logic/dma/prompt_loader.py` (4 occurrences)
- Other DMA files

## Refactoring Strategy for Each Agent

1. **Identify the purpose** of each Dict[str, Any] usage
2. **Create specific Pydantic models** based on actual data structure
3. **Replace Dict[str, Any]** with the new model
4. **Update imports** and type annotations
5. **Test the changes** to ensure compatibility

## Common Patterns to Replace

### Pattern 1: Configuration Data
```python
# Before
config: Dict[str, Any] = {...}

# After
from pydantic import BaseModel

class ServiceConfig(BaseModel):
    endpoint: str
    timeout: int
    retry_count: int = 3
    
config: ServiceConfig = ServiceConfig(...)
```

### Pattern 2: API Response Data
```python
# Before
def get_data() -> Dict[str, Any]:
    return {"status": "ok", "data": [...]}

# After
class ApiResponse(BaseModel):
    status: str
    data: List[DataItem]
    error: Optional[str] = None
    
def get_data() -> ApiResponse:
    return ApiResponse(status="ok", data=[...])
```

### Pattern 3: Context Data
```python
# Before
context: Dict[str, Any] = {
    "user_id": "123",
    "channel": "discord",
    "metadata": {...}
}

# After
class RequestContext(BaseModel):
    user_id: str
    channel: str
    metadata: Dict[str, str]  # Still dict but with specific value type
```

## Notes
- Start with high-impact files (most occurrences)
- Create shared models in appropriate schema modules
- Use inheritance for related models
- Add validation where beneficial
- Keep backwards compatibility during migration