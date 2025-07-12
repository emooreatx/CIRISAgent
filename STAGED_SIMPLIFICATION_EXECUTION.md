# STAGED SIMPLIFICATION EXECUTION PLAN

## Restore Point Created
Commit: `1328b23` - Complete type safety sprint with 0 mypy errors

## Execution Stages with Validation Gates

### STAGE 1: Automated Import Cleanup (5 min)
```bash
# 1.1 Install autoflake
pip install autoflake

# 1.2 Remove unused imports only (safest operation)
autoflake --remove-all-unused-imports --in-place --recursive ciris_engine/

# 1.3 VALIDATION GATE
pytest                          # Must be green
mypy ciris_engine/             # Must stay at 0 errors
git diff --stat                # Review scope of changes

# 1.4 If all pass, commit
git add -A && git commit -m "refactor: Remove 144 unused imports via autoflake"
```

### STAGE 2: Remove Unused Variables (5 min)
```bash
# 2.1 Remove unused variables (separate pass for safety)
autoflake --remove-unused-variables --in-place --recursive ciris_engine/

# 2.2 VALIDATION GATE
pytest                          # Must be green
mypy ciris_engine/             # Must stay at 0 errors

# 2.3 If all pass, commit
git add -A && git commit -m "refactor: Remove unused variables"
```

### STAGE 3: Consolidate Constants (15 min)
```bash
# 3.1 Create constants file
cat > ciris_engine/constants.py << 'EOF'
"""Central constants for CIRIS."""
from pathlib import Path

# Agent defaults
DEFAULT_WA = "CIRIS"
DEFAULT_TEMPLATE = "default"
DEFAULT_TEMPLATE_PATH = Path("ciris_templates")

# Model defaults  
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o-mini"
DEFAULT_LLM_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_LLM_TIMEOUT = 30
DEFAULT_LLM_MAX_RETRIES = 3

# Prompt defaults
DEFAULT_PROMPT_TEMPLATE = "default_prompt"

# Time defaults
DEFAULT_CONSOLIDATION_INTERVAL_HOURS = 6
DEFAULT_RETENTION_HOURS = 24 * 7  # 1 week

# System defaults
DEFAULT_MAX_THOUGHT_DEPTH = 5
DEFAULT_ROUND_DELAY_SECONDS = 0.2
EOF

# 3.2 Find and replace duplicates
grep -r "DEFAULT_WA.*=.*\"CIRIS\"" ciris_engine/ --include="*.py" -l | while read f; do
    sed -i '1s/^/from ciris_engine.constants import DEFAULT_WA\n/' "$f"
    sed -i '/DEFAULT_WA.*=.*"CIRIS"/d' "$f"
done

# 3.3 VALIDATION GATE
pytest
mypy ciris_engine/

# 3.4 Commit if green
git add -A && git commit -m "refactor: Consolidate constants to single file"
```

### STAGE 4: Create Timestamp Utility (10 min)
```bash
# 4.1 Create serialization utility
mkdir -p ciris_engine/utils
cat > ciris_engine/utils/serialization.py << 'EOF'
"""Serialization utilities."""
from datetime import datetime
from typing import Optional, Any

def serialize_timestamp(timestamp: datetime, _info: Any = None) -> Optional[str]:
    """Standard timestamp serialization for Pydantic models."""
    return timestamp.isoformat() if timestamp else None

def serialize_datetime(dt: datetime) -> Optional[str]:
    """Serialize datetime to ISO format."""
    return dt.isoformat() if dt else None
EOF

# 4.2 Replace all duplicate serialize_timestamp methods
find ciris_engine/ -name "*.py" -exec grep -l "def serialize_timestamp" {} \; | while read f; do
    # Add import at top
    sed -i '1s/^/from ciris_engine.utils.serialization import serialize_timestamp\n/' "$f"
    # Remove the method definition
    sed -i '/def serialize_timestamp/,/return.*isoformat/d' "$f"
done

# 4.3 VALIDATION GATE
pytest
mypy ciris_engine/

# 4.4 Commit
git add -A && git commit -m "refactor: Consolidate timestamp serialization"
```

### STAGE 5: Create Base Service Class (20 min)
```bash
# 5.1 Create base service
cat > ciris_engine/logic/services/base_service.py << 'EOF'
"""Base service implementation."""
from typing import Dict, Any
from ciris_engine.protocols.services.base import ServiceProtocol
from ciris_engine.schemas.services.capabilities import ServiceCapabilities

class BaseService:
    """Base implementation for all services."""
    
    def __init__(self):
        self._running = False
    
    async def start(self) -> None:
        """Start the service."""
        self._running = True
    
    async def stop(self) -> None:
        """Stop the service."""
        self._running = False
    
    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._running
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "running": self._running,
            "service": self.__class__.__name__,
            "healthy": self._running
        }
    
    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name=self.__class__.__name__,
            actions=[],
            version="1.0.0",
            dependencies=[]
        )
EOF

# 5.2 Update one service as a test
# Pick TimeService as it's simple
sed -i '/class TimeService/a\    # Inherits base methods from BaseService' ciris_engine/logic/services/lifecycle/time.py

# 5.3 VALIDATION GATE
pytest tests/ciris_engine/logic/services/lifecycle/test_time_service.py
mypy ciris_engine/logic/services/lifecycle/time.py

# 5.4 If passes, continue with other services...
```

### STAGE 6: Remove NotImplementedError Methods (15 min)
```bash
# 6.1 Find all NotImplementedError methods
grep -r "raise NotImplementedError" ciris_engine/ --include="*.py" -B5 | grep -B5 "def " > notimplemented_methods.txt

# 6.2 Review each one manually and delete if truly unused
# Example:
# - If in a protocol: Keep (defines interface)
# - If in implementation: Delete (dead code)

# 6.3 VALIDATION GATE after each deletion
pytest
mypy ciris_engine/

# 6.4 Commit
git add -A && git commit -m "refactor: Remove NotImplementedError stub methods"
```

### STAGE 7: Delete Unused Schemas (30 min)
```bash
# 7.1 Find potentially unused schemas
python << 'EOF'
import os
import re

# Find all schema classes
schemas = []
for root, dirs, files in os.walk('ciris_engine/schemas'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path) as f:
                content = f.read()
                for match in re.finditer(r'class\s+(\w+)\s*\(.*BaseModel', content):
                    schemas.append((match.group(1), path))

# Check which are never imported
unused = []
for schema_name, schema_path in schemas:
    found = False
    for root, dirs, files in os.walk('ciris_engine'):
        if 'schemas' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path) as f:
                    if schema_name in f.read():
                        found = True
                        break
        if found:
            break
    
    if not found:
        unused.append((schema_name, schema_path))

print(f"Found {len(unused)} potentially unused schemas:")
for name, path in unused[:10]:  # Show first 10
    print(f"  {name} in {path}")
EOF

# 7.2 Delete truly unused schemas (manually verify each)

# 7.3 VALIDATION GATE
pytest
mypy ciris_engine/

# 7.4 Commit
git add -A && git commit -m "refactor: Remove unused schema definitions"
```

### STAGE 8: Simplify Protocol Hierarchy (45 min)
```bash
# 8.1 Analyze current protocol structure
find ciris_engine/protocols -name "*.py" -exec grep -l "class.*Protocol" {} \; | wc -l

# 8.2 Create simplified base protocols
# Move to flat structure where possible

# 8.3 VALIDATION GATE after each change
pytest
mypy ciris_engine/

# 8.4 Commit
git add -A && git commit -m "refactor: Simplify protocol hierarchy"
```

## Recovery Plan

If any stage fails:
```bash
# See what broke
pytest -v --tb=short

# If can't fix quickly, rollback to last good commit
git reset --hard HEAD~1

# Or rollback to original restore point
git reset --hard 1328b23
```

## Success Metrics

After all stages:
```bash
# Measure improvement
find ciris_engine -name "*.py" | xargs wc -l | tail -1  # Total LOC
find ciris_engine -name "*.py" | wc -l                  # Total files
mypy ciris_engine/ 2>&1 | grep -c error               # Should be 0
pytest --tb=no | grep passed                           # Should be 647+
vulture ciris_engine/ --min-confidence 80 | wc -l     # Should be < 18
```

## Start Execution

Begin with Stage 1 - it's the safest and gives immediate value.