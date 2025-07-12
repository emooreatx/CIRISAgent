# CIRIS Simplification Action Plan

## Immediate Wins (Safe to Execute Now)

### 1. Remove All Unused Imports (144 total)
```bash
# Install and run autoflake
pip install autoflake
autoflake --remove-all-unused-imports --in-place --recursive ciris_engine/
```

### 2. Consolidate Duplicate Constants
Create `ciris_engine/constants.py`:
```python
# Agent defaults
DEFAULT_WA = "CIRIS"
DEFAULT_TEMPLATE = "default"
DEFAULT_TEMPLATE_PATH = Path("ciris_templates")

# Model defaults  
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o-mini"
DEFAULT_PROMPT_TEMPLATE = "default_prompt"
```
Remove 25+ duplicate definitions across files.

### 3. Create Timestamp Utility
Create `ciris_engine/utils/serialization.py`:
```python
def serialize_timestamp(timestamp: datetime, _info: Any) -> Optional[str]:
    """Standard timestamp serialization for Pydantic models."""
    return timestamp.isoformat() if timestamp else None
```
Replace 11 duplicate implementations.

### 4. Remove Unused Protocol Parameters
In protocol definitions, remove parameter names:
```python
# Before
async def send_message(self, channel: str, content: str, author: str) -> None:

# After  
async def send_message(self, str, str, str) -> None:
```

## Medium Priority (Requires Review)

### 5. Remove Unimplemented Adapter Protocols
Delete these unused protocol files:
- `protocols/adapters/slack.py`
- `protocols/adapters/matrix.py` 
- `protocols/adapters/websocket.py`

### 6. Consolidate Service Base Methods
Create `ServiceBaseMixin`:
```python
class ServiceBaseMixin:
    """Common implementation for all services."""
    async def start(self) -> None:
        self._running = True
        
    async def stop(self) -> None:
        self._running = False
        
    async def is_healthy(self) -> bool:
        return self._running
        
    def get_status(self) -> Dict[str, Any]:
        return {"running": self._running}
```
Reduces 50+ duplicate implementations.

### 7. Remove NotImplementedError Stubs
Either implement or delete these 9 methods entirely.

### 8. Complete or Remove TODOs
Address 13 TODO comments - either implement or create GitHub issues.

## Architecture Simplification

### 9. Schema Consolidation
Look for patterns in 564 BaseModel schemas:
- Merge similar response models
- Use generic types where appropriate
- Remove unused API response models

### 10. Protocol Hierarchy Simplification
```python
# Create cleaner protocol inheritance
class GraphServiceProtocol(ServiceProtocol):
    """Combines base service with graph operations."""
    def get_node_type(self) -> str: ...
    def query_graph(self, query: MemoryQuery) -> List[GraphNode]: ...
    def store_in_graph(self, node: GraphNode) -> str: ...
```

## What NOT to Remove

### Critical Safety Features (Keep Despite "Unused")
- Emergency shutdown endpoints
- Audit trail methods
- Authentication decorators
- Rate limiting middleware

### Future Extensibility (Keep)
- The 19-service architecture
- Protocol definitions for core interfaces
- Bus system for multi-provider support
- Handler infrastructure

### API Endpoints (Verify First)
Check SDK usage before removing any "unused" API endpoints.

## Execution Order

1. **Today**: Run autoflake for imports (instant win)
2. **Today**: Consolidate constants and timestamps
3. **Tomorrow**: Create ServiceBaseMixin 
4. **This Week**: Schema consolidation
5. **Next Sprint**: Architecture refinements

## Expected Results

- **-5% code size** (mostly imports)
- **-100+ duplicate methods**
- **Clearer codebase** for contributors
- **Maintained functionality** 
- **Better type safety** (fewer Any imports)

## Validation

After each step:
1. Run mypy - should stay at 0 errors
2. Run pytest - all tests green
3. Run vulture - verify reductions
4. Check Docker build still works

This plan prioritizes safety and simplicity while maintaining the sophisticated architecture needed for future scaling.