#!/usr/bin/env python3
"""Fix handler_name parameter in TSDBConsolidationService"""

import re

# Read the file
with open('/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/tsdb_consolidation_service.py', 'r') as f:
    content = f.read()

# Replace patterns
# 1. recall with handler_name
content = re.sub(
    r'await self\._memory_bus\.recall\(([^)]+), handler_name="tsdb_consolidation"\)',
    r'await self._memory_bus.recall(\1)',
    content
)

# 2. memorize with handler_name
content = re.sub(
    r'await self\._memory_bus\.memorize\(([^)]+), handler_name="tsdb_consolidation"\)',
    r'await self._memory_bus.memorize(\1)',
    content
)

# 3. Multi-line memorize calls
content = re.sub(
    r'(\s+)handler_name="tsdb_consolidation"',
    r'\1# handler_name removed - not supported by memory service',
    content
)

# Write back
with open('/home/emoore/CIRISAgent/ciris_engine/logic/services/graph/tsdb_consolidation_service.py', 'w') as f:
    f.write(content)

print("Fixed all handler_name occurrences in TSDBConsolidationService")