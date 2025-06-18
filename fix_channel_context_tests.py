#!/usr/bin/env python3
"""Script to update test files to use ChannelContext instead of channel_id."""

import os
import re
from pathlib import Path


def update_speak_params(content):
    """Update SpeakParams to use channel_context."""
    # Pattern 1: SpeakParams(content=..., channel_id=...)
    pattern1 = r'SpeakParams\(([^)]*?)channel_id=([^,)]+)'
    def replace1(match):
        params = match.group(1)
        channel_value = match.group(2).strip()
        # Add import if needed
        return f'SpeakParams({params}channel_context=create_channel_context({channel_value})'
    
    content = re.sub(pattern1, replace1, content)
    
    # Pattern 2: channel_id= in keyword arguments
    pattern2 = r'(SpeakParams\([^)]*)"channel_id":\s*([^,}]+)'
    def replace2(match):
        prefix = match.group(1)
        channel_value = match.group(2).strip()
        return f'{prefix}"channel_context": create_channel_context({channel_value})'
    
    content = re.sub(pattern2, replace2, content)
    
    return content


def update_observe_params(content):
    """Update ObserveParams to use channel_context."""
    # Pattern: ObserveParams(...channel_id=...)
    pattern = r'ObserveParams\(([^)]*?)channel_id=([^,)]+)'
    def replace(match):
        params = match.group(1)
        channel_value = match.group(2).strip()
        return f'ObserveParams({params}channel_context=create_channel_context({channel_value})'
    
    return re.sub(pattern, replace, content)


def update_dispatch_context(content):
    """Update DispatchContext creation to use channel_context."""
    # Pattern: DispatchContext(...channel_id=...)
    pattern = r'DispatchContext\(([^)]*?)channel_id=([^,)]+)'
    def replace(match):
        params = match.group(1)
        channel_value = match.group(2).strip()
        return f'DispatchContext({params}channel_context=create_channel_context({channel_value})'
    
    return re.sub(pattern, replace, content)


def add_imports(content):
    """Add channel_utils import if needed."""
    if 'create_channel_context' in content and 'from ciris_engine.utils.channel_utils import' not in content:
        # Find the last import line
        import_lines = []
        lines = content.split('\n')
        last_import_idx = 0
        
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_idx = i
        
        # Insert the new import after the last import
        lines.insert(last_import_idx + 1, 'from ciris_engine.utils.channel_utils import create_channel_context')
        content = '\n'.join(lines)
    
    return content


def process_file(filepath):
    """Process a single file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Apply updates
    content = update_speak_params(content)
    content = update_observe_params(content)
    content = update_dispatch_context(content)
    
    # Add imports if needed
    if content != original_content:
        content = add_imports(content)
    
    # Write back if changed
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Updated: {filepath}")
        return True
    
    return False


def main():
    """Main function."""
    test_dir = Path('tests')
    updated_count = 0
    
    for filepath in test_dir.rglob('*.py'):
        if process_file(filepath):
            updated_count += 1
    
    print(f"\nTotal files updated: {updated_count}")


if __name__ == '__main__':
    main()