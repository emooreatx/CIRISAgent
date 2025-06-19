#!/usr/bin/env python3
"""
Fix observer constructors in test files.
Replace multi_service_sink parameter with bus_manager.
"""

import os
import re
from pathlib import Path

# Files to fix
files_to_fix = [
    "tests/ciris_engine/action_handlers/test_observe_active_channel.py",
    "tests/ciris_engine/dma/action_selection/test_action_instruction_generator.py",
    "tests/adapters/api/test_api_platform.py",
    "tests/adapters/cli/test_cli_adapter.py",
    "tests/adapters/cli/test_cli_platform.py",
    "tests/ciris_engine/adapters/discord/test_discord_comprehensive.py",
    "tests/ciris_engine/adapters/discord/test_discord_observer.py",
    "tests/ciris_engine/adapters/discord/test_discord_platform.py",
    "tests/ciris_engine/adapters/test_base_observer.py",
    "tests/adapters/api/test_api_adapter.py"
]

def fix_file(filepath):
    """Fix observer constructors in a single file."""
    print(f"Processing {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace multi_service_sink with bus_manager in constructors
    content = re.sub(r'multi_service_sink\s*=', 'bus_manager=', content)
    
    # Also fix any variable names if they exist
    content = re.sub(r'multi_service_sink\s*:', 'bus_manager:', content)
    
    # Fix imports if needed - replace MultiServiceSink with BusManager
    if "MultiServiceSink" in content:
        # Add BusManager import if not present
        if "BusManager" not in content and "message_buses" not in content:
            # Find where to add the import
            sink_import_match = re.search(r'from ciris_engine\.sinks.*import.*MultiServiceSink', content)
            if sink_import_match:
                # Replace the sink import with bus manager import
                content = re.sub(
                    r'from ciris_engine\.sinks.*import.*MultiServiceSink',
                    'from ciris_engine.message_buses import BusManager',
                    content
                )
            else:
                # Add after other ciris_engine imports
                content = re.sub(
                    r'(from ciris_engine\.[^\n]+\n)',
                    r'\1from ciris_engine.message_buses import BusManager\n',
                    content,
                    count=1
                )
        
        # Replace MultiServiceSink type annotations with BusManager
        content = re.sub(r'MultiServiceSink', 'BusManager', content)
    
    # Fix any mock creations
    content = re.sub(r'mock_multi_service_sink', 'mock_bus_manager', content)
    content = re.sub(r'Mock\(\s*spec\s*=\s*MultiServiceSink\s*\)', 'Mock(spec=BusManager)', content)
    
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