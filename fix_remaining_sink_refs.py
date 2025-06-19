#!/usr/bin/env python3
"""
Fix remaining multi_service_sink references in tests.
"""

import os
import re
from pathlib import Path

# Files to fix based on grep results
files_to_fix = [
    "tests/adapters/cli/test_cli_platform.py",
    "tests/adapters/cli/test_cli_adapter.py", 
    "tests/adapters/api/test_api_platform.py",
    "tests/ciris_engine/adapters/discord/test_discord_observer.py",
    "tests/ciris_engine/adapters/discord/test_discord_comprehensive.py"
]

def fix_file(filepath):
    """Fix multi_service_sink references in a single file."""
    print(f"Processing {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace multi_service_sink with bus_manager
    # But not in comments or TODO lines
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if 'multi_service_sink' in line and not line.strip().startswith('#'):
            # Replace multi_service_sink with bus_manager
            new_line = line.replace('multi_service_sink', 'bus_manager')
            new_lines.append(new_line)
        else:
            new_lines.append(line)
    
    new_content = '\n'.join(new_lines)
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print(f"Fixed {filepath}")

def main():
    """Fix all files."""
    for filepath in files_to_fix:
        if os.path.exists(filepath):
            fix_file(filepath)
        else:
            print(f"Warning: {filepath} not found")
    
    print("\nAll files processed!")

if __name__ == "__main__":
    main()