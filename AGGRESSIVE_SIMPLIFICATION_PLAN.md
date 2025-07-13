# AGGRESSIVE SIMPLIFICATION EXECUTION PLAN

## Philosophy: Less Code = Less Bugs = More Reliable

For mission-critical systems, every line of code is a potential failure point. Let's aggressively remove everything not actively used.

## PHASE 1: IMMEDIATE AUTOMATED REMOVAL (Execute Now)

### 1.1 Remove All Unused Imports (144 files)
```bash
# This is safe and will reduce cognitive load
autoflake --remove-all-unused-imports --in-place --recursive ciris_engine/

# Also remove unused variables in the same pass
autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive ciris_engine/
```

### 1.2 Delete Entire Unused Protocol Files
```bash
# These adapter protocols have ZERO implementations
rm ciris_engine/protocols/adapters/slack.py
rm ciris_engine/protocols/adapters/matrix.py
rm ciris_engine/protocols/adapters/websocket.py

# These DMA protocols are never used
find ciris_engine/protocols/dma -name "*.py" -exec grep -l "Protocol" {} \; | while read f; do
    # Check if any implementation exists
    protocol_name=$(grep "class.*Protocol" "$f" | awk '{print $2}' | cut -d'(' -f1)
    if ! grep -r "$protocol_name" ciris_engine/logic/ --include="*.py" | grep -v "Protocol" | grep -q .; then
        echo "DELETE: $f (no implementation found)"
    fi
done
```

### 1.3 Remove All NotImplementedError Methods
```bash
# Find and delete all methods that just raise NotImplementedError
# These are dead weight - if we need them, we'll add them when we implement them
grep -r "raise NotImplementedError" ciris_engine/ --include="*.py" -B5 | grep "def "
# Then manually delete each method (safer than automated)
```

## PHASE 2: AGGRESSIVE CONSOLIDATION (Today)

### 2.1 Create Minimal Base Classes
```python
# ciris_engine/logic/services/base_service.py
class BaseService:
    """Minimal base for all services."""
    def __init__(self):
        self._running = False
    
    async def start(self) -> None:
        self._running = True
    
    async def stop(self) -> None:
        self._running = False
    
    async def is_healthy(self) -> bool:
        return self._running
    
    def get_status(self) -> Dict[str, Any]:
        return {"running": self._running, "service": self.__class__.__name__}
    
    def get_capabilities(self) -> ServiceCapabilities:
        return ServiceCapabilities(
            service_name=self.__class__.__name__,
            actions=[],
            version="1.0.0",
            dependencies=[]
        )
```

Then DELETE 50+ duplicate implementations and inherit from BaseService.

### 2.2 Delete Duplicate Serializers
```python
# ciris_engine/utils/serialization.py
def serialize_timestamp(timestamp: datetime) -> Optional[str]:
    """The ONE timestamp serializer."""
    return timestamp.isoformat() if timestamp else None
```

Delete ALL 11 duplicate implementations. Use this ONE function.

### 2.3 Merge Duplicate Constants
```python
# ciris_engine/constants.py - The ONLY place for constants
DEFAULT_WA = "CIRIS"
DEFAULT_TEMPLATE = "default"
# ... etc
```

Delete ALL duplicate constant definitions across 25+ files.

## PHASE 3: SCHEMA MASSACRE (This Week)

### 3.1 Identify Unused Schemas
```bash
# Find all Pydantic models
grep -r "class.*BaseModel" ciris_engine/schemas/ | wc -l  # 564!

# Find which are never imported
for schema in $(grep -r "class.*BaseModel" ciris_engine/schemas/ | awk '{print $2}' | cut -d'(' -f1); do
    if ! grep -r "import.*$schema" ciris_engine/ | grep -v "schemas/" | grep -q .; then
        echo "UNUSED SCHEMA: $schema"
    fi
done
```

### 3.2 Merge Similar Schemas
- Look for schemas with <3 field differences
- Create generic versions where possible
- Example: 5 different "Response" models → 1 GenericResponse

### 3.3 Delete Test-Only Schemas
Any schema only used in tests should be defined IN the test file, not in production code.

## PHASE 4: API ENDPOINT AUDIT (This Week)

### 4.1 Track Actual Usage
```python
# Add temporary logging to all endpoints
@router.post("/interact")
async def interact(...):
    logger.info("ENDPOINT_USED: /interact")  # Temporary
    # ... rest of endpoint
```

Run for 24 hours, then DELETE any endpoint not called.

### 4.2 Remove Duplicate Endpoints
Several endpoints do similar things:
- Multiple ways to get status
- Multiple ways to query memory
- Multiple ways to get config

Keep ONE way to do each thing.

## PHASE 5: ARCHITECTURAL CUTS (Next Week)

### 5.1 Protocol Simplification
Instead of complex protocol hierarchies:
```python
# BEFORE: 35 protocols with complex inheritance
class ServiceProtocol(Protocol): ...
class GraphServiceProtocol(ServiceProtocol): ...
class AuditServiceProtocol(GraphServiceProtocol): ...

# AFTER: Flat and simple
class ServiceProtocol(Protocol):
    """ALL services implement these methods."""
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def is_healthy(self) -> bool: ...
    def get_status(self) -> Dict[str, Any]: ...
    def get_capabilities(self) -> ServiceCapabilities: ...

# Service-specific protocols only for unique methods
class MemoryServiceProtocol(Protocol):
    async def memorize(self, node: GraphNode) -> str: ...
    async def recall(self, node_id: str) -> Optional[GraphNode]: ...
```

### 5.2 Remove Theoretical Features
- Delete all "future" code paths
- Delete all "might need this" abstractions
- Delete all "just in case" handlers

## VALIDATION AFTER EACH PHASE

```bash
# Must pass after EVERY change
pytest                          # All green
mypy ciris_engine/             # 0 errors
docker build -t ciris-test .   # Builds successfully
vulture ciris_engine/ --min-confidence 80  # Fewer findings each time
```

## EXPECTED RESULTS

### Before
- 435 source files
- ~50,000 lines of code
- 564 Pydantic schemas
- 144 unused imports
- 50+ duplicate methods

### After Aggressive Simplification
- ~350 source files (-20%)
- ~40,000 lines of code (-20%)
- ~300 Pydantic schemas (-47%)
- 0 unused imports
- 0 duplicate methods

## THE GOLDEN RULE

**If you can't explain why a piece of code exists in 10 seconds, DELETE IT.**

Mission-critical systems need clarity, not cleverness. Every line should have a clear purpose TODAY, not theoretical value tomorrow.

## START NOW

```bash
# Execute Phase 1.1 immediately:
pip install autoflake
autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive ciris_engine/

# Then run tests to ensure nothing broke:
pytest
```

After each deletion, if tests pass, commit immediately. Small, frequent commits make rollback easy if needed.