#!/usr/bin/env python3
"""
Fix observe handler test calls to _recall_from_messages
"""
import re

def fix_test_file(filepath):
    """Fix _recall_from_messages calls in test file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace calls that pass mock_memory_service as first arg
    content = re.sub(
        r'await observe_handler\._recall_from_messages\(mock_memory_service, ([^,]+), ([^)]+)\)',
        r'await observe_handler._recall_from_messages(\1, \2)',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Fixed {filepath}")

# Fix the test files
test_files = [
    'tests/test_observe_handler_recall_logic.py',
    'tests/integration/test_observe_handler_integration.py'
]

for file in test_files:
    try:
        fix_test_file(file)
    except Exception as e:
        print(f"Error fixing {file}: {e}")