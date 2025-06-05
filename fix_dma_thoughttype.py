#!/usr/bin/env python3
"""Fix ThoughtType usage in DMA tests."""

import re
from pathlib import Path

def fix_dma_tests():
    """Fix ThoughtType in DMA test files."""
    test_files = [
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/dma/test_dma_executor.py"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/dma/test_csdma.py"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/dma/test_pdma.py"),
        Path("/home/emoore/CIRISAgent/tests/ciris_engine/dma/test_action_selection_pdma.py"),
    ]
    
    for test_file in test_files:
        if test_file.exists():
            content = test_file.read_text()
            original = content
            
            # Add ThoughtType import if needed
            if 'from ciris_engine.schemas.foundational_schemas_v1 import' in content and 'ThoughtType' not in content:
                content = re.sub(
                    r'from ciris_engine\.schemas\.foundational_schemas_v1 import ([^)]+)',
                    r'from ciris_engine.schemas.foundational_schemas_v1 import \1, ThoughtType',
                    content
                )
            elif 'ThoughtType' not in content:
                # Add import line if no existing import
                content = re.sub(
                    r'(from ciris_engine\.schemas\.agent_core_schemas_v1 import [^\n]+\n)',
                    r'\1from ciris_engine.schemas.foundational_schemas_v1 import ThoughtType\n',
                    content
                )
            
            # Fix string thought_type assignments
            content = re.sub(r'thought_type="test"', 'thought_type=ThoughtType.STANDARD', content)
            content = re.sub(r"thought_type='test'", 'thought_type=ThoughtType.STANDARD', content)
            
            if content != original:
                test_file.write_text(content)
                print(f"Fixed {test_file}")

if __name__ == "__main__":
    fix_dma_tests()
    print("Completed fixing ThoughtType usage in DMA tests")