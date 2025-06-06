#!/usr/bin/env python3
"""Fix ThoughtType usage in processor tests."""

import re
from pathlib import Path

def fix_thought_type_imports_and_usage(file_path: Path):
    """Fix ThoughtType imports and string usage."""
    content = file_path.read_text()
    original = content
    
    # Add ThoughtType import if needed
    if 'from ciris_engine.schemas.foundational_schemas_v1 import' in content and 'ThoughtType' not in content:
        content = re.sub(
            r'from ciris_engine\.schemas\.foundational_schemas_v1 import ([^)]+)',
            r'from ciris_engine.schemas.foundational_schemas_v1 import \1, ThoughtType',
            content
        )
    
    # Fix string thought_type assignments
    content = re.sub(r'thought_type="test"', 'thought_type=ThoughtType.STANDARD', content)
    content = re.sub(r'thought_type="human_interaction"', 'thought_type=ThoughtType.STANDARD', content)
    content = re.sub(r'thought_type="standard"', 'thought_type=ThoughtType.STANDARD', content)
    content = re.sub(r"thought_type='test'", 'thought_type=ThoughtType.STANDARD', content)
    content = re.sub(r"thought_type='standard'", 'thought_type=ThoughtType.STANDARD', content)
    
    if content != original:
        file_path.write_text(content)
        print(f"Fixed {file_path}")
        return True
    return False

def fix_processor_tests():
    """Fix all processor test files with ThoughtType issues."""
    test_files = [
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/processor/test_pydantic_serialization.py"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/processor/test_base_processor.py"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/processor/test_guardrail_bypass_prevention.py"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/processor/test_processor_states.py"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/processor/test_observe_processing.py"),
    ]
    
    for test_file in test_files:
        if test_file.exists():
            fix_thought_type_imports_and_usage(test_file)

if __name__ == "__main__":
    fix_processor_tests()
    print("Completed fixing ThoughtType usage in processor tests")