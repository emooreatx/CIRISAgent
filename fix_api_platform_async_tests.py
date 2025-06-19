#!/usr/bin/env python3
"""
Add @pytest.mark.asyncio to all async test methods in test_api_platform.py
"""

import re
from pathlib import Path

def fix_async_tests(filepath):
    """Add pytest.mark.asyncio decorator to async test methods."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern to find async def test methods without the decorator
    # Look for lines that have async def test but not preceded by @pytest.mark.asyncio
    lines = content.split('\n')
    new_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is an async test method
        if re.match(r'^\s*async def test', line):
            # Check if previous line is already a pytest decorator
            prev_line = lines[i-1] if i > 0 else ""
            if '@pytest.mark.asyncio' not in prev_line:
                # Add the decorator with proper indentation
                indent = re.match(r'^(\s*)', line).group(1)
                new_lines.append(f'{indent}@pytest.mark.asyncio')
        
        new_lines.append(line)
        i += 1
    
    new_content = '\n'.join(new_lines)
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print(f"Fixed {filepath}")

def main():
    filepath = "tests/adapters/api/test_api_platform.py"
    fix_async_tests(filepath)

if __name__ == "__main__":
    main()