#!/usr/bin/env python3
"""
Fix simple unused imports one at a time.
Only removes imports that are on their own line.
"""
import re
import os


# List of known unused imports from flake8 output
UNUSED_IMPORTS = [
    ("ciris_engine/logic/adapters/api/api_communication.py", 212, "FetchedMessage"),
    ("ciris_engine/logic/adapters/api/routes/agent.py", 783, "json"),
    ("ciris_engine/logic/adapters/api/api_observer.py", 5, "Optional"),
    ("ciris_engine/logic/adapters/api/api_observer.py", 5, "Any"),
    ("ciris_engine/logic/adapters/api/api_runtime_control.py", 11, "AdapterOperationResult"),
    ("ciris_engine/logic/adapters/api/api_runtime_control.py", 11, "AdapterStatus as AdapterStatusSchema"),
    ("ciris_engine/logic/adapters/api/api_tools.py", 7, "Any"),
    ("ciris_engine/logic/adapters/api/config.py", 4, "Optional"),
    ("ciris_engine/logic/adapters/api/middleware/rate_limiter.py", 6, "HTTPException"),
    ("ciris_engine/logic/adapters/api/middleware/rate_limiter.py", 11, "defaultdict"),
    ("ciris_engine/logic/adapters/api/routes/agent.py", 9, "cast"),
    ("ciris_engine/logic/adapters/api/routes/audit.py", 7, "Dict"),
    ("ciris_engine/logic/adapters/api/routes/emergency.py", 29, "ServiceRegistry"),
    ("ciris_engine/logic/adapters/api/routes/system.py", 7, "Union"),
    ("ciris_engine/logic/adapters/api/routes/system_extensions.py", 7, "datetime"),
]


def remove_import_from_file(filepath, line_num, import_name):
    """Remove a specific import from a file."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return False
        
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Adjust for 0-based indexing
    idx = line_num - 1
    
    if idx >= len(lines):
        print(f"Line {line_num} out of range in {filepath}")
        return False
    
    original_line = lines[idx]
    
    # Handle different import patterns
    if f"import {import_name}" in original_line and original_line.strip() == f"import {import_name}":
        # Simple import on its own line
        lines.pop(idx)
        modified = True
    elif f"from " in original_line and import_name in original_line:
        # Check if it's a single import on its own line
        if original_line.strip().endswith(f"import {import_name}"):
            lines.pop(idx)
            modified = True
        else:
            # Multiple imports or complex pattern
            print(f"Skipping complex import at {filepath}:{line_num}")
            return False
    else:
        print(f"Could not match import pattern at {filepath}:{line_num}")
        return False
    
    # Write back
    with open(filepath, 'w') as f:
        f.writelines(lines)
    
    print(f"Removed '{import_name}' from {filepath}:{line_num}")
    return True


def main():
    """Process all unused imports."""
    removed = 0
    
    for filepath, line_num, import_name in UNUSED_IMPORTS:
        if remove_import_from_file(filepath, line_num, import_name):
            removed += 1
    
    print(f"\nTotal removed: {removed}/{len(UNUSED_IMPORTS)}")


if __name__ == "__main__":
    main()