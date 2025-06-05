#!/usr/bin/env python3
"""Fix GraphNode usage in test files where string/bool types are expected."""

import re
from pathlib import Path

def fix_graphnode_content_fields(file_path: Path):
    """Fix GraphNode used for content fields that should be strings."""
    content = file_path.read_text()
    original = content
    
    # Fix SpeakParams content
    content = re.sub(
        r'SpeakParams\(\s*content=GraphNode\([^)]+\),\s*channel_id=([^)]+)\)',
        r'SpeakParams(content="Hello, world!", channel_id=\1)',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fix RejectParams reason 
    content = re.sub(
        r'RejectParams\(\s*reason=GraphNode\([^)]+\)\)',
        r'RejectParams(reason="Not relevant to the task")',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fix DeferParams reason
    content = re.sub(
        r'DeferParams\(\s*reason=GraphNode\([^)]+\)([^)]*)\)',
        r'DeferParams(reason="Need more information"\1)',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fix ForgetParams reason
    content = re.sub(
        r'ForgetParams\(\s*node=([^,]+),\s*reason=GraphNode\([^)]+\)\)',
        r'ForgetParams(node=\1, reason="No longer needed")',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fix ToolParams name
    content = re.sub(
        r'ToolParams\(\s*name=GraphNode\([^)]+\)',
        r'ToolParams(name="test_tool"',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fix ObserveParams active and context
    content = re.sub(
        r'ObserveParams\(\s*active=GraphNode\([^)]+\),([^)]*),\s*context=GraphNode\([^)]+\)\)',
        r'ObserveParams(active=True,\1, context={"source": "test"})',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fix GraphNode id field using NodeType enum instead of string
    content = re.sub(
        r'GraphNode\(\s*id=NodeType\.([A-Z]+)',
        r'GraphNode(id="\1".lower()',
        content
    )
    
    # Fix any remaining id=NodeType patterns
    content = re.sub(
        r'id=NodeType\.([A-Z_]+)',
        r'id="\1".lower().replace("_", "")',
        content
    )
    
    if content != original:
        file_path.write_text(content)
        print(f"Fixed {file_path}")
        return True
    return False

def fix_test_files():
    """Fix all test files with GraphNode issues."""
    test_dirs = [
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/action_handlers"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/processor"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/schemas"),
        Path("/home/emoore/CIRISAgent/tests/integration"),
    ]
    
    for test_dir in test_dirs:
        if test_dir.exists():
            for test_file in test_dir.glob("*.py"):
                fix_graphnode_content_fields(test_file)

if __name__ == "__main__":
    fix_test_files()
    print("Completed fixing GraphNode usage in test files")