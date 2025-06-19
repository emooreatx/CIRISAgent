#!/usr/bin/env python3
"""
Fix ActionHandlerDependencies constructor in all test files.
Replace service_registry parameter with bus_manager.
"""

import os
import re
from pathlib import Path

# Files to fix
files_to_fix = [
    "tests/ciris_engine/action_handlers/test_speak_handler.py",
    "tests/test_thought_depth_propagation.py", 
    "tests/ciris_engine/action_handlers/test_defer_handler.py",
    "tests/ciris_engine/action_handlers/test_followup_thoughts.py",
    "tests/test_observe_handler_recall_logic.py"
]

def fix_file(filepath):
    """Fix ActionHandlerDependencies usage in a single file."""
    print(f"Processing {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if file needs BusManager import
    if "BusManager" not in content and "ActionHandlerDependencies" in content:
        # Add BusManager import after ServiceRegistry import
        content = re.sub(
            r'(from ciris_engine\.registries\.base import .*ServiceRegistry.*)',
            r'\1\nfrom ciris_engine.message_buses import BusManager',
            content
        )
    
    # Replace ActionHandlerDependencies constructor calls
    # Pattern 1: deps = ActionHandlerDependencies(service_registry=service_registry)
    pattern1 = r'(\s+)(deps = ActionHandlerDependencies\(service_registry=service_registry\))'
    replacement1 = r'\1bus_manager = BusManager(service_registry)\n\1deps = ActionHandlerDependencies(bus_manager=bus_manager)'
    content = re.sub(pattern1, replacement1, content)
    
    # Pattern 2: dependencies = ActionHandlerDependencies(service_registry=registry)
    pattern2 = r'(\s+)(dependencies = ActionHandlerDependencies\(service_registry=([^)]+)\))'
    def replace_deps(match):
        indent = match.group(1)
        registry_var = match.group(3)
        return f'{indent}bus_manager = BusManager({registry_var})\n{indent}dependencies = ActionHandlerDependencies(bus_manager=bus_manager)'
    
    content = re.sub(pattern2, replace_deps, content)
    
    # Pattern 3: ActionHandlerDependencies(service_registry=...)
    # For any other variations
    pattern3 = r'ActionHandlerDependencies\(service_registry=([^)]+)\)'
    matches = list(re.finditer(pattern3, content))
    
    # Process matches in reverse order to maintain positions
    for match in reversed(matches):
        registry_var = match.group(1)
        # Find the line start for proper indentation
        line_start = content.rfind('\n', 0, match.start()) + 1
        line = content[line_start:match.start()]
        indent = re.match(r'(\s*)', line).group(1)
        
        # Check if this is already fixed
        if 'bus_manager = BusManager' not in content[line_start-100:match.start()]:
            # Insert bus_manager creation before this line
            new_line = f'{indent}bus_manager = BusManager({registry_var})\n'
            content = content[:line_start] + new_line + content[line_start:]
            # Update the ActionHandlerDependencies call
            new_call = f'ActionHandlerDependencies(bus_manager=bus_manager)'
            content = content[:match.start() + len(new_line)] + new_call + content[match.end() + len(new_line):]
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Fixed {filepath}")

def main():
    """Fix all test files."""
    for filepath in files_to_fix:
        if os.path.exists(filepath):
            fix_file(filepath)
        else:
            print(f"Warning: {filepath} not found")
    
    print("\nAll files processed!")

if __name__ == "__main__":
    main()