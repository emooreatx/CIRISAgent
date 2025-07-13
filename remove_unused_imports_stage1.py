#!/usr/bin/env python3
"""
Stage 1: Remove unused imports identified by flake8.
Only removes simple, single imports that are safe to remove.
"""
import re
import os


# List of unused imports to remove (from flake8 output)
UNUSED_IMPORTS = [
    # API adapter imports
    ("ciris_engine/logic/adapters/api/adapter.py", "Optional", "from typing"),
    ("ciris_engine/logic/adapters/api/adapter.py", "asynccontextmanager", "from contextlib"),
    ("ciris_engine/logic/adapters/api/adapter.py", "FastAPI", "from fastapi"),
    ("ciris_engine/logic/adapters/api/adapter.py", "CORSMiddleware", "from fastapi.middleware.cors"),
    ("ciris_engine/logic/adapters/api/api_observer.py", "Optional", "from typing"),
    ("ciris_engine/logic/adapters/api/api_observer.py", "Any", "from typing"),
    ("ciris_engine/logic/adapters/api/api_tools.py", "Any", "from typing"),
    ("ciris_engine/logic/adapters/api/routes/agent.py", "cast", "from typing"),
    ("ciris_engine/logic/adapters/api/routes/audit.py", "Dict", "from typing"),
    ("ciris_engine/logic/adapters/api/routes/system.py", "Union", "from typing"),
    ("ciris_engine/logic/adapters/api/routes/telemetry.py", "Path", "from fastapi"),
    ("ciris_engine/logic/adapters/api/routes/telemetry.py", "TimeSyncStatus", "from ciris_engine.schemas.api.telemetry"),
    ("ciris_engine/logic/adapters/api/routes/telemetry.py", "ServiceMetrics", "from ciris_engine.schemas.api.telemetry"),
    ("ciris_engine/logic/adapters/api/routes/telemetry_logs_reader.py", "os", "import os"),
    ("ciris_engine/logic/adapters/api/routes/telemetry_metrics.py", "List", "from typing"),
    ("ciris_engine/logic/adapters/api/routes/wa.py", "Dict", "from typing"),
    ("ciris_engine/logic/adapters/api/routes/wa.py", "Any", "from typing"),
    ("ciris_engine/logic/adapters/api/services/auth_service.py", "Any", "from typing"),
    
    # Base adapter imports
    ("ciris_engine/logic/adapters/base_adapter.py", "FetchedMessage", "from ciris_engine.schemas.runtime.messages"),
    ("ciris_engine/logic/adapters/base_observer.py", "persistence", "import ciris_engine.logic.persistence"),
    
    # Discord adapter imports
    ("ciris_engine/logic/adapters/discord/discord_observer.py", "persistence", "import ciris_engine.logic.persistence"),
    ("ciris_engine/logic/adapters/discord/discord_tool_handler.py", "MetricData", "from ciris_engine.schemas.telemetry.core"),
    ("ciris_engine/logic/adapters/discord/discord_tool_handler.py", "LogData", "from ciris_engine.schemas.telemetry.core"),
    ("ciris_engine/logic/adapters/discord/discord_tool_handler.py", "TraceContext", "from ciris_engine.schemas.telemetry.core"),
    ("ciris_engine/logic/adapters/discord/discord_tool_service.py", "asyncio", "import asyncio"),
    
    # Bus imports
    ("ciris_engine/logic/buses/llm_bus.py", "time", "import time"),
    ("ciris_engine/logic/buses/runtime_control_bus.py", "cast", "from typing"),
    
    # Other imports
    ("ciris_engine/logic/conscience/core.py", "TYPE_CHECKING", "from typing"),
    ("ciris_engine/logic/conscience/thought_depth_guardrail.py", "datetime", "from datetime"),
    ("ciris_engine/logic/conscience/thought_depth_guardrail.py", "timezone", "from datetime"),
    ("ciris_engine/logic/context/batch_context.py", "Tuple", "from typing"),
    ("ciris_engine/logic/context/batch_context.py", "datetime", "from datetime"),
    ("ciris_engine/logic/context/system_snapshot.py", "TaskStatus", "from ciris_engine.schemas.runtime.enums"),
    ("ciris_engine/logic/dma/csdma.py", "cast", "from typing"),
    ("ciris_engine/logic/dma/dma_executor.py", "Union", "from typing"),
    ("ciris_engine/logic/dma/dma_executor.py", "datetime", "from datetime"),
    ("ciris_engine/logic/dma/dma_executor.py", "timezone", "from datetime"),
]


def remove_import(filepath, import_name, import_type):
    """Remove a specific import from a file."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return False
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    modified = False
    new_lines = []
    
    for line in lines:
        # Skip the line if it's the import we want to remove
        if import_type == "import" and line.strip() == f"import {import_name}":
            print(f"  Removing: {line.strip()}")
            modified = True
            continue
        elif import_type.startswith("from") and import_name in line:
            # Check if this is the right import line
            if f"import {import_name}" in line or f"import ({import_name}" in line:
                # Check if it's a multi-import line
                if "," in line:
                    # Handle multi-import removal
                    parts = line.split("import")[1].strip()
                    imports = [i.strip() for i in parts.split(",")]
                    imports = [i for i in imports if not i.startswith(import_name)]
                    if imports:
                        new_line = line.split("import")[0] + "import " + ", ".join(imports) + "\n"
                        new_lines.append(new_line)
                        print(f"  Modified: {line.strip()} -> {new_line.strip()}")
                    else:
                        print(f"  Removing: {line.strip()}")
                    modified = True
                    continue
                else:
                    # Single import line
                    print(f"  Removing: {line.strip()}")
                    modified = True
                    continue
        
        new_lines.append(line)
    
    if modified:
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
        return True
    
    return False


def main():
    """Remove all unused imports."""
    print("Stage 1: Removing unused imports\n")
    
    removed_count = 0
    
    for filepath, import_name, import_type in UNUSED_IMPORTS:
        print(f"Processing {filepath}:")
        if remove_import(filepath, import_name, import_type):
            removed_count += 1
        else:
            print(f"  No changes made")
        print()
    
    print(f"\nTotal imports removed: {removed_count}")
    print("\nNext steps:")
    print("1. Run: pytest")
    print("2. Run: mypy ciris_engine/")
    print("3. If all pass, commit changes")


if __name__ == "__main__":
    main()